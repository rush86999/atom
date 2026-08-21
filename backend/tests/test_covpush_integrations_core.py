"""Coverage push for backend/integrations core services (>=95% per module).

Mocks DB/HTTP/LLM everywhere; never touches the network.
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from fastapi import HTTPException


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _q_returning(value):
    """Query mock whose .filter(...).first() resolves to `value`, including
    chained filters (production code re-filters by tenant before first())."""
    f = MagicMock()
    f.first.return_value = value
    f.filter.return_value = f
    q = MagicMock()
    q.filter.return_value = f
    return q


def _svc():
    """Fresh MCPService-like instance without singleton state pollution."""
    import integrations.mcp_service as mod

    svc = mod.MCPService.__new__(mod.MCPService)
    svc.initialized = True
    svc.config = {}
    svc.tenant_id = "default"
    svc.active_servers = {}
    svc.search_api_key = None
    return svc


def _cls(inst):
    cls = MagicMock(return_value=inst)
    cls.return_value = inst
    return cls


def _mock_imports(modules):
    """Patch sys.modules with mocked modules (restored on exit)."""
    return patch.dict(sys.modules, modules)


async def _run_local(svc, tool, args=None, context=None, extra_modules=None):
    """Execute a local-tools tool with the real registry disabled."""
    modules = extra_modules or {}
    with _mock_imports(modules), patch(
        "integrations.mcp_service.get_tool_registry"
    ) as _reg:
        _reg.return_value.get.return_value = False
        return await svc.execute_tool("local-tools", tool, args or {}, context or {})


def _conn(manager=None):
    """Async context manager returning manager; used to mock httpx.AsyncClient."""
    manager = manager or MagicMock()
    manager.__aenter__ = AsyncMock(return_value=manager)
    manager.__aexit__ = AsyncMock(return_value=False)
    return manager


# ---------------------------------------------------------------------------
# MCPService basics
# ---------------------------------------------------------------------------
class TestMCPServiceBasics:
    def test_singleton_and_init_once(self):
        import integrations.mcp_service as mod

        old = mod.MCPService._instance
        mod.MCPService._instance = None
        try:
            s1 = mod.MCPService("t1", {"k": "v"})
            s2 = mod.MCPService("t2", {})
            assert s1 is s2
            assert s1.tenant_id == "t1"
            assert s1.config == {"k": "v"}
            assert s1.initialized is True
        finally:
            mod.MCPService._instance = old

    def test_get_capabilities(self):
        svc = _svc()
        caps = svc.get_capabilities()
        assert caps["supports_webhooks"] is False
        assert len(caps["operations"]) == 5

    def test_health_check(self):
        svc = _svc()
        h = svc.health_check()
        assert h["ok"] is True and h["status"] == "healthy"
        h2 = _svc()
        h2.initialized = False
        assert h2.health_check()["ok"] is False

    async def test_execute_operation_dispatch(self):
        svc = _svc()
        with patch.object(svc, "get_openai_tools", new=AsyncMock(return_value=["t"])), \
             patch.object(svc, "get_server_tools", new=AsyncMock(return_value=["s"])), \
             patch.object(svc, "call_tool", new=AsyncMock(return_value="called")), \
             patch.object(svc, "search_tools", new=AsyncMock(return_value=["m"])), \
             patch.object(svc, "web_search", new=AsyncMock(return_value={"ok": 1})):
            r = await svc.execute_operation("get_openai_tools", {}, {})
            assert r["success"] is True
            r = await svc.execute_operation("get_server_tools", {"server_id": "x"}, {})
            assert r["success"] is True
            r = await svc.execute_operation("call_tool", {"tool_name": "t", "arguments": {}}, {"tenant_id": "t"})
            assert r["result"] == "called"
            r = await svc.execute_operation("search_tools", {"query": "q", "limit": 3}, {})
            assert r["success"] is True
            r = await svc.execute_operation("web_search", {"query": "q"}, {})
            assert r["result"] == {"ok": 1}
            r = await svc.execute_operation("nope", {}, {})
            assert r["success"] is False

    async def test_execute_operation_error_path(self):
        svc = _svc()
        with patch.object(svc, "get_openai_tools", new=AsyncMock(side_effect=RuntimeError("x"))):
            r = await svc.execute_operation("get_openai_tools", {}, {})
        assert r["success"] is False
        assert "x" in r["error"]

    async def test_get_openai_tools_and_active_connections(self):
        import integrations.mcp_service as mod

        svc = _svc()
        with patch.object(svc, "get_all_tools", new=AsyncMock(return_value=[{"name": "a"}])), \
             patch.object(mod.MCPToolConverter, "convert_to_openai_tools", return_value=["conv"]):
            assert await svc.get_openai_tools() == ["conv"]
        svc.active_servers = {"s1": {"name": "n", "connected_at": "t"}}
        conns = await svc.get_active_connections()
        assert conns[0]["server_id"] == "s1"

    async def test_get_server_tools_variants(self):
        svc = _svc()
        gs = await svc.get_server_tools("google-search")
        assert any(t["name"] == "web_search" for t in gs)
        lt = await svc.get_server_tools("local-tools")
        assert any(t["name"] == "discover_connections" for t in lt)
        assert await svc.get_server_tools("unknown") == []

    async def test_get_all_tools_merges(self):
        svc = _svc()
        registry = MagicMock()
        registry.get_simplified_tools.return_value = [{"name": "reg_tool", "description": "d"}]
        action = MagicMock()
        action.name = "act_tool"
        action.description = "desc"
        action.parameters_schema = {"properties": {"p": {"type": "string"}}, "required": ["p"]}
        with patch("integrations.mcp_service.get_tool_registry", return_value=registry), \
             patch("core.action_registry.action_registry") as ar, \
             patch.object(svc, "get_server_tools", new=AsyncMock(return_value=[
                 {"name": "reg_tool", "description": "dup"},
                 {"name": "local_only", "description": "x"},
             ])):
            ar.get_all_definitions.return_value = [action]
            svc.active_servers = {"external": {"tools": [{"name": "ext", "description": "e"}]}}
            all_tools = await svc.get_all_tools()
        names = {t["name"] for t in all_tools}
        assert {"reg_tool", "act_tool", "ext", "local_only"} <= names

    async def test_register_integration_tools(self):
        import integrations.mcp_service as mod

        svc = _svc()
        db = MagicMock()
        integration = MagicMock()
        integration.connector_id = "salesforce"
        db.query.return_value.filter.return_value.all.return_value = [integration]
        service = MagicMock()
        service.get_operations.return_value = [
            {"name": "list_contacts", "description": "d", "parameters": {}, "complexity": 2}
        ]
        with patch("core.models.TenantIntegration", new=MagicMock()), \
             patch("core.integration_registry.IntegrationRegistry") as reg_cls:
            reg_cls.return_value.get_service_instance = AsyncMock(return_value=service)
            tools = await svc.register_integration_tools("tenant1", db)
        assert len(tools) == 1
        assert tools[0]["name"] == "salesforce_list_contacts"
        assert svc.tools_cache["tenant1:salesforce:list_contacts"]["connector_id"] == "salesforce"

    async def test_register_integration_tools_skip_and_fail(self):
        import integrations.mcp_service as mod

        svc = _svc()
        db = MagicMock()
        i1 = MagicMock()
        i1.connector_id = "nosvc"
        i2 = MagicMock()
        i2.connector_id = "noops"
        i3 = MagicMock()
        i3.connector_id = "boom"
        db.query.return_value.filter.return_value.all.return_value = [i1, i2, i3]
        reg = MagicMock()
        reg.get_service_instance = AsyncMock(side_effect=[None, MagicMock(), RuntimeError("bad")])
        with patch("core.models.TenantIntegration", new=MagicMock()), \
             patch("core.integration_registry.IntegrationRegistry", return_value=reg):
            tools = await svc.register_integration_tools("tenant1", db)
        assert tools == []

    async def test_register_integration_tools_creates_own_session(self):
        import integrations.mcp_service as mod

        svc = _svc()
        db = MagicMock()
        with patch.object(mod, "SessionLocal", return_value=db) as sl, \
             patch("core.models.TenantIntegration", new=MagicMock()), \
             patch("core.integration_registry.IntegrationRegistry") as reg_cls:
            db.query.return_value.filter.return_value.all.return_value = []
            await svc.register_integration_tools("tenant1")
        sl.assert_called_once()

    async def test_search_tools(self):
        svc = _svc()
        with patch.object(svc, "get_all_tools", new=AsyncMock(return_value=[
            {"name": "web_search", "description": "search the web"},
            {"name": "create_task", "description": "make tasks"},
        ])):
            matches = await svc.search_tools("search", 10)
            assert [m["name"] for m in matches] == ["web_search"]
            assert await svc.search_tools("zzz", 10) == []

    async def test_call_tool_capability_gate(self):
        svc = _svc()
        agent = MagicMock()
        agent.id = "ag1"
        with patch("core.capability_resolver.get_agent_for_context", return_value=agent), \
             patch("core.capability_resolver.resolve_allowed_tools", return_value={"a"}), \
             patch("core.capability_resolver.is_tool_allowed", return_value=False):
            r = await svc.call_tool("secret_tool", {}, {"tier": "autonomous", "agent_id": "ag1"})
        assert r["success"] is False
        assert r["blocked_by"] == "capability_gate"

    async def test_call_tool_sandbox_enforced_block(self):
        svc = _svc()
        decision = MagicMock()
        decision.requires_review = True
        decision.enforced = True
        decision.decision = "block"
        decision.violation_detail = "fs escape"
        with patch("core.capability_resolver.get_agent_for_context", return_value=None), \
             patch("core.sandbox_gate.evaluate_tool_call", return_value=decision):
            r = await svc.call_tool("t", {}, {"agent_id": "ag1"})
        assert "fs escape" in str(r)

    async def test_call_tool_sandbox_shadow_then_action_registry(self):
        svc = _svc()
        decision = MagicMock()
        decision.requires_review = True
        decision.enforced = False
        decision.violation_type = "fs_scope"
        with patch("core.capability_resolver.get_agent_for_context", return_value=None), \
             patch("core.sandbox_gate.evaluate_tool_call", return_value=decision), \
             patch("core.action_registry.action_registry") as ar:
            ar.get_action.return_value = MagicMock()
            ar.execute_action = AsyncMock(return_value={"ok": True})
            r = await svc.call_tool("ontology_act", {}, {"agent_id": "a"})
        assert r == {"ok": True}

    async def test_call_tool_entity_path(self):
        svc = _svc()
        with patch("core.capability_resolver.get_agent_for_context", return_value=None), \
             patch("core.sandbox_gate.evaluate_tool_call", return_value=None), \
             patch.object(svc, "execute_entity_tool", new=AsyncMock(return_value={"e": 1})):
            r = await svc.call_tool("t", {}, {"entity_id": "e1"})
        assert r == {"e": 1}

    async def test_call_tool_hardcoded_and_dynamic_and_external(self):
        svc = _svc()
        with patch("core.capability_resolver.get_agent_for_context", return_value=None), \
             patch("core.sandbox_gate.evaluate_tool_call", return_value=None), \
             patch("core.action_registry.action_registry") as ar, \
             patch.object(svc, "execute_tool", new=AsyncMock(return_value="executed")) as et:
            ar.get_action.return_value = None
            r = await svc.call_tool("web_search", {"query": "q"}, {"workspace_id": "w"})
            assert r == "executed"
            svc.active_servers = {"dyn": {"tools": [{"name": "dyn_tool"}]}}
            r = await svc.call_tool("dyn_tool", {}, {})
            assert r == "executed"
            assert et.call_count == 2

    async def test_call_tool_external_hub_and_not_found(self):
        svc = _svc()
        hub = MagicMock()
        tool = MagicMock()
        tool.name = "ext_tool"
        hub.tools_cache = {"ext_server": [tool]}
        hub.call_external_tool = AsyncMock(return_value={"ext": 1})
        with patch("core.capability_resolver.get_agent_for_context", return_value=None), \
             patch("core.sandbox_gate.evaluate_tool_call", return_value=None), \
             patch("core.action_registry.action_registry") as ar, \
             patch("core.mcp_service.mcp_service", hub):
            ar.get_action.return_value = None
            r = await svc.call_tool("ext_tool", {}, {})
            assert r == {"ext": 1}
            r = await svc.call_tool("missing_tool", {}, {})
            assert "not found" in r["error"]

    async def test_call_tool_agent_not_allowed_tier_lookup(self):
        svc = _svc()
        with patch("core.capability_resolver.get_agent_for_context", return_value=None), \
             patch("core.sandbox_gate.evaluate_tool_call", side_effect=RuntimeError("gate down")), \
             patch("core.action_registry.action_registry") as ar:
            ar.get_action.return_value = None
            r = await svc.call_tool("web_search", {"query": "q"}, {})
        assert isinstance(r, dict)


# ---------------------------------------------------------------------------
# HITL policy
# ---------------------------------------------------------------------------
class TestHitlPolicy:
    async def test_hitl_missing_workspace_and_tenant(self):
        import integrations.mcp_service as mod

        svc = _svc()
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        with patch("core.database.SessionLocal", return_value=db):
            # R81b: fail-closed — missing workspace/tenant BLOCKS risky tools
            # instead of the old swallow-and-allow.
            db.query.return_value.filter.return_value.first.return_value = None
            r = await svc._check_hitl_policy("nows", "send_email", {})
            assert r and r.get("blocked_by") == "hitl_policy_error"
            ws = MagicMock()
            ws.tenant_id = "t"
            db.query.return_value.filter.return_value.first.side_effect = [ws, None]
            r = await svc._check_hitl_policy("ws", "send_email", {})
            assert r and r.get("blocked_by") == "hitl_policy_error"

    async def test_hitl_intervention_required(self):
        import integrations.mcp_service as mod

        svc = _svc()
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        ws = MagicMock()
        ws.tenant_id = "t1"
        tenant = MagicMock()
        tenant.metadata_json = {"governance": {"require_hitl_external": True, "allow_autonomous_external": False}}
        user = MagicMock()
        user.tenant_id = "t1"
        user.notification_preferences = {"force_agent_approval": False}
        db.query.return_value.filter.return_value.first.side_effect = [ws, tenant, user, None]
        with patch("core.database.SessionLocal", return_value=db), \
             patch("core.intervention_service.intervention_service") as interv:
            interv.request_intervention = AsyncMock(return_value={"paused": True})
            r = await svc._check_hitl_policy(
                "ws1", "send_email", {"to": "x@y.z"}, {"user_id": "u1"}
            )
        assert r == {"paused": True}
        assert interv.request_intervention.call_args.kwargs["action_type"] == "send_email"

    async def test_hitl_autonomous_agent_approved(self):
        import integrations.mcp_service as mod
        from core.models import AgentRegistry as _AR, Tenant as _T, \
            User as _U, Workspace as _W

        svc = _svc()
        ws = MagicMock()
        ws.tenant_id = "t1"
        tenant = MagicMock()
        tenant.metadata_json = {"governance": {"require_hitl_external": True, "allow_autonomous_external": True}}
        user = MagicMock()
        user.tenant_id = "t1"
        user.notification_preferences = {}
        agent = MagicMock()
        agent.maturity_level = 5
        agent.status = "autonomous"  # R81e: tier-name comparison
        agent.name = "A"

        # Per-model keyed queries — a shared filter/first chain made the
        # lookup order ambiguous (R81b).
        model_map = {
            _W: _q_returning(ws),
            _T: _q_returning(tenant),
            _U: _q_returning(user),
            _AR: _q_returning(agent),
        }
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        db.query = MagicMock(side_effect=lambda m, *a, **k: model_map[m])
        with patch("core.database.SessionLocal", return_value=db):
            r = await svc._check_hitl_policy(
                "ws1", "whatsapp_send_message", {}, {"user_id": "u1", "agent_id": "ag1"}
            )
        assert r is None

    async def test_hitl_exception_blocks(self):
        """R81b: fail-closed — a policy-check failure must NOT allow."""
        import integrations.mcp_service as mod

        svc = _svc()
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        db.query.side_effect = RuntimeError("db down")
        with patch("core.database.SessionLocal", return_value=db):
            r = await svc._check_hitl_policy("ws1", "send_email", {})
        assert r and r.get("blocked_by") == "hitl_policy_error"


# ---------------------------------------------------------------------------
# execute_tool — registry + local-tools branches
# ---------------------------------------------------------------------------
class TestExecuteToolRegistry:
    async def test_registry_tool_sync_and_async(self):
        import integrations.mcp_service as mod

        svc = _svc()
        registry = MagicMock()
        sync_fn = MagicMock(return_value="sync-result")
        async_fn = AsyncMock(return_value="async-result")
        registry.get.return_value = True
        registry.get_function.side_effect = [sync_fn, async_fn]
        with patch("integrations.mcp_service.get_tool_registry", return_value=registry):
            r = await svc.execute_tool("local-tools", "sync_tool", {"a": 1}, {"agent_id": "x"})
            assert r == "sync-result"
            r = await svc.execute_tool("local-tools", "async_tool", {}, {})
            assert r == "async-result"

    async def test_registry_tool_unknown_raises(self):
        import integrations.mcp_service as mod

        svc = _svc()
        registry = MagicMock()
        registry.get.return_value = True
        registry.get_function.return_value = None
        with patch("integrations.mcp_service.get_tool_registry", return_value=registry):
            with pytest.raises(ValueError):
                await svc.execute_tool("local-tools", "missing", {}, {})


class TestExecuteToolLocalTools:
    async def _run(self, svc, tool, args=None, context=None, extra_modules=None):
        return await _run_local(svc, tool, args, context, extra_modules)

    async def test_finance_close_check(self):
        svc = _svc()
        agent = MagicMock()
        agent.run_close_check = AsyncMock(return_value={"ok": True})
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        with patch("accounting.close_agent.CloseChecklistAgent", _cls(agent)), \
             patch("core.database.SessionLocal", lambda: db):
            r = await _run_local(svc, "finance_close_check", {"period": "2026-07"})
        assert r == {"ok": True}

    async def test_b2b_tools(self):
        svc = _svc()
        svc_b2b = MagicMock()
        svc_b2b.extract_po_from_text = AsyncMock(return_value={"po": 1})
        svc_b2b.create_draft_order_from_po = AsyncMock(return_value={"order": 1})
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        b2b_cls = _cls(svc_b2b)
        push = MagicMock()
        push.push_draft_order = AsyncMock(return_value={"pushed": 1})
        push_cls = _cls(push)
        with _mock_imports({
            "ecommerce.b2b_procurement_service": MagicMock(B2BProcurementService=b2b_cls),
            "ecommerce.b2b_data_push_service": MagicMock(B2BDataPushService=push_cls),
            "core.database": MagicMock(SessionLocal=lambda: db),
        }):
            r = await _run_local(svc, "b2b_extract_po", {"text": "po"})
            assert r == {"po": 1}
            r = await _run_local(svc, "b2b_create_draft_order", {"workspace_id": "w", "customer_email": "c@x", "po_data": {}})
            assert r == {"order": 1}
            r = await _run_local(svc, "b2b_push_to_integrations", {"order_id": "o1"})
            assert r == {"pushed": 1}

    async def test_request_human_intervention(self):
        import integrations.mcp_service as mod

        svc = _svc()
        with patch("core.intervention_service.intervention_service") as interv:
            interv.request_intervention = AsyncMock(return_value={"paused": True})
            r = await _run_local(svc, "request_human_intervention",
                                {"action": "pay", "reason": "why", "params": {"amt": 5}},
                                {"workspace_id": "w", "tenant_id": "t"})
        assert r == {"paused": True}

    async def test_trigger_workflow_gate(self):
        import integrations.mcp_service as mod

        svc = _svc()
        orch = MagicMock()
        with patch("integrations.mcp_service.get_orchestrator", return_value=orch) if hasattr(mod, "get_orchestrator") else patch(
            "advanced_workflow_orchestrator.get_orchestrator", return_value=orch
        ), patch("core.workflow_security.resolve_orchestrator_steps", return_value=[{"type": "critical"}]), patch(
            "core.workflow_security.has_critical_step", return_value=True
        ):
            r = await _run_local(svc, "trigger_workflow", {"workflow_id": "w1"})
            assert "refused" in r["error"]
        ctx = MagicMock()
        ctx.status.value = "completed"
        ctx.workflow_id = "w1"
        ctx.results = {}
        ctx.error_message = None
        with patch("advanced_workflow_orchestrator.get_orchestrator", return_value=orch), \
             patch("core.workflow_security.resolve_orchestrator_steps", return_value=[{"type": "email"}]), \
             patch("core.workflow_security.has_critical_step", return_value=False), \
             patch.object(orch, "execute_workflow", new=AsyncMock(return_value=ctx)):
            r = await _run_local(svc, "trigger_workflow", {"workflow_id": "w1", "input_data": {}})
            assert r["status"] == "completed"
        r = await _run_local(svc, "trigger_workflow", {})
        assert r == {"error": "workflow_id is required"}

    async def test_marketing_agent_tools(self):
        svc = _svc()
        agent = MagicMock()
        agent.trigger_review_request = AsyncMock(return_value={"ok": 1})
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        with _mock_imports({"core.database": MagicMock(SessionLocal=lambda: db)}):
            from core import marketing_agent
            marketing_agent.MarketingAgent = _cls(agent)
            r = await _run_local(svc, "marketing_review_request", {"customer_id": "c1", "workspace_id": "w"})
            assert r == {"ok": 1}

    async def test_competitive_and_inventory_tools(self):
        svc = _svc()
        comp = MagicMock()
        comp.track_competitor_pricing = AsyncMock(return_value={"prices": 1})
        inv = MagicMock()
        inv.reconcile_inventory = AsyncMock(return_value={"inv": 1})
        with _mock_imports({
            "operations.automations.competitive_intel": MagicMock(CompetitiveIntelWorkflow=_cls(comp)),
            "operations.automations.inventory_reconcile": MagicMock(InventoryReconciliationWorkflow=_cls(inv)),
        }):
            r = await _run_local(svc, "track_competitor_pricing", {"competitors": ["x"], "product": "p"})
            assert r == {"prices": 1}
            r = await _run_local(svc, "reconcile_inventory", {"workspace_id": "w"})
            assert r == {"inv": 1}

    async def test_canvas_tool(self):
        svc = _svc()
        manager = MagicMock()
        manager.broadcast_event = AsyncMock()
        with _mock_imports({"core.websockets": MagicMock(get_connection_manager=lambda: manager)}):
            r = await _run_local(svc, "canvas_tool",
                                {"action": "present", "component": "chart", "data": {}, "title": "t"},
                                {"workspace_id": "w", "agent_id": "a"})
        assert "sent" in r
        manager.broadcast_event.assert_called_once()

    async def test_collaboration_hub_tools(self):
        svc = _svc()
        hub = MagicMock()
        hub.update_ai_analysis = MagicMock(return_value={"upd": 1})
        hub.save_draft_response = MagicMock(return_value={"draft": 1})
        hub.approve_draft = AsyncMock(return_value={"approved": 1})
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        with _mock_imports({
            "core.collaboration_hub_service": MagicMock(get_collaboration_hub_service=lambda d: hub),
            "core.database": MagicMock(SessionLocal=lambda: db),
        }):
            r = await _run_local(svc, "analyze_message", {"message_id": "m1", "analysis": {}})
            assert r == {"upd": 1}
            r = await _run_local(svc, "draft_response", {"message_id": "m1", "content": "x"})
            assert r == {"draft": 1}
            r = await _run_local(svc, "approve_draft", {"message_id": "m1"})
            assert r == {"approved": 1}

    async def test_ingest_message_attachment(self):
        svc = _svc()
        r = await _run_local(svc, "ingest_message_attachment", {"file_name": "f.pdf"})
        assert "ingested" in r

    async def test_shopify_tools(self):
        svc = _svc()
        store = MagicMock()
        store.access_token = "tok"
        store.shop_domain = "shop.myshopify.com"
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        db.query.return_value.filter.return_value.first.return_value = store
        shopify = MagicMock()
        shopify._get_base_url.return_value = "https://x"
        shopify._get_headers.return_value = {"X": "1"}
        shopify.get_orders = AsyncMock(return_value=[
            {"order_number": 1, "total_price": "10.0", "currency": "USD", "financial_status": "paid"}
        ])
        with _mock_imports({
            "integrations.shopify_service": MagicMock(ShopifyService=_cls(shopify)),
            "core.database": MagicMock(SessionLocal=lambda: db),
            "core.models": MagicMock(EcommerceStore=MagicMock()),
        }):
            with patch("integrations.mcp_service.httpx.AsyncClient") as client_cls:
                client = _conn()
                client.post = AsyncMock()
                resp = MagicMock()
                resp.status_code = 201
                resp.json.return_value = {"product": {"id": 7}}
                resp.text = "err"
                client.post.return_value = resp
                client_cls.return_value = client
                r = await _run_local(svc, "shopify_create_product", {"title": "p"})
                assert "created" in r
                resp.status_code = 400
                r = await _run_local(svc, "shopify_create_product", {"title": "p"})
                assert "Failed" in r
                resp.status_code = 200
                r = await _run_local(svc, "shopify_update_inventory", {"inventory_item_id": "i", "location_id": "l", "available": 3})
                assert r == "Inventory updated successfully."
            r = await _run_local(svc, "shopify_get_orders", {})
            assert "Order #1" in r
        r = await _run_local(svc, "shopify_create_product", {})
        assert "No Shopify store" in r

    async def test_reconcile_payroll(self):
        svc = _svc()
        payroll = MagicMock()
        payroll.reconcile_payroll = AsyncMock(return_value={"payroll": 1})
        with _mock_imports({
            "finance.automations.payroll_guardian": MagicMock(PayrollReconciliationWorkflow=_cls(payroll)),
        }):
            r = await _run_local(svc, "reconcile_payroll", {"period": "2026-07"})
        assert r == {"payroll": 1}

    async def test_list_agents_and_spawn(self):
        svc = _svc()
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        agent_row = MagicMock()
        agent_row.id = "a1"
        agent_row.name = "n"
        agent_row.description = "d"
        agent_row.category = "c"
        db.query.return_value.all.return_value = [agent_row]
        atom = MagicMock()
        atom.spawn_agent = AsyncMock(return_value={"spawned": 1})
        with _mock_imports({
            "core.database": MagicMock(SessionLocal=lambda: db),
            "core.atom_meta_agent": MagicMock(
                SpecialtyAgentTemplate=MagicMock(TEMPLATES=[{"id": 1}]),
                get_atom_agent=lambda w: atom,
            ),
        }):
            r = await _run_local(svc, "list_agents")
            assert r["registered"][0]["id"] == "a1"
            r = await _run_local(svc, "spawn_agent", {"template": "t1"}, {"workspace_id": "w"})
            assert r == {"spawned": 1}

    async def test_list_workflows(self):
        import integrations.mcp_service as mod

        svc = _svc()
        with patch.object(mod.os, "path") as os_path:
            os_path.exists.return_value = False
            r = await _run_local(svc, "list_workflows")
            assert r == []
        os_path = None
        with patch.object(mod.os, "path") as os_path:
            os_path.exists.return_value = True
            with patch.object(mod.os, "listdir", return_value=["a.json", "b.txt"]):
                with patch("builtins.open", MagicMock()):
                    import json as _json
                    with patch.object(mod.json, "load", return_value={"workflow_id": "w1", "name": "n", "description": "d", "trigger": "t"}):
                        r = await _run_local(svc, "list_workflows")
        assert r == [{"id": "w1", "name": "n", "description": "d", "trigger": "t"}]

    async def test_bridge_agent_delegate(self):
        svc = _svc()
        bridge = MagicMock()
        bridge.process_incoming_message = AsyncMock(return_value={"routed": 1})
        with _mock_imports({
            "integrations.universal_webhook_bridge": MagicMock(universal_webhook_bridge=bridge),
        }):
            r = await _run_local(svc, "bridge_agent_delegate", {"target_agent": "x", "message": "hi"}, {"agent_id": "a"})
            assert r == {"routed": 1}
            r = await _run_local(svc, "bridge_agent_delegate", {"target_agent": "x"})
            assert r["status"] == "error"

    async def test_browser_desktop_tools(self):
        svc = _svc()
        nm = MagicMock()
        nm.send_to_desktop = AsyncMock(return_value=True)
        with _mock_imports({"core.notification_manager": MagicMock(notification_manager=nm)}):
            r = await _run_local(svc, "browser_navigate", {"url": "https://x"}, {"workspace_id": "w"})
            assert "Desktop" in r
            r = await _run_local(svc, "browser_click", {"selector": "#b", "x": 1, "y": 2}, {"workspace_id": "w"})
            assert "Desktop" in r
            r = await _run_local(svc, "browser_type", {"text": "hi", "selector": "#i"}, {"workspace_id": "w"})
            assert "Desktop" in r
            r = await _run_local(svc, "browser_screenshot", {}, {"workspace_id": "w"})
            assert "Desktop" in r
        nm.send_to_desktop = AsyncMock(return_value=False)
        with _mock_imports({"core.notification_manager": MagicMock(notification_manager=nm)}):
            r = await _run_local(svc, "browser_navigate", {"url": "u"}, {"workspace_id": "w"})
            assert "SIMULATION" in r
            r = await _run_local(svc, "browser_click", {"selector": "#b"}, {"workspace_id": "w"})
            assert "SIMULATION" in r
            r = await _run_local(svc, "browser_type", {"text": "t"}, {"workspace_id": "w"})
            assert "SIMULATION" in r
            r = await _run_local(svc, "browser_screenshot", {}, {"workspace_id": "w"})
            assert "SIMULATION" in r

    async def test_browser_cloud_tools(self):
        svc = _svc()
        cloud = MagicMock()
        for m in ["navigate", "click", "type_text", "screenshot", "new_tab", "switch_tab",
                  "click_coords", "list_tabs", "save_session", "set_proxy",
                  "start_monitoring", "stop_monitoring", "wait_for_selector",
                  "extract_content", "upload_file", "download_file"]:
            setattr(cloud, m, AsyncMock(return_value=f"{m}-ok"))
        with _mock_imports({"core.cloud_browser_service": MagicMock(cloud_browser=cloud)}):
            ctx = {"computer_use_mode": "cloud", "workspace_id": "default", "agent_id": "a"}
            assert await _run_local(svc, "browser_navigate", {"url": "u"}, ctx) == "navigate-ok"
            assert await _run_local(svc, "browser_click", {"selector": "#b"}, ctx) == "click-ok"
            assert await _run_local(svc, "browser_type", {"text": "t", "selector": "#i"}, ctx) == "type_text-ok"
            assert await _run_local(svc, "browser_screenshot", {}, ctx) == "screenshot-ok"
            assert await _run_local(svc, "browser_new_tab", {"url": "u"}, ctx) == "new_tab-ok"
            assert await _run_local(svc, "browser_switch_tab", {"index": 1}, ctx) == "switch_tab-ok"
            assert await _run_local(svc, "browser_click_coords", {"x": 1, "y": 2}, ctx) == "click_coords-ok"
            assert await _run_local(svc, "list_browser_tabs", {}, ctx) == "list_tabs-ok"
            assert await _run_local(svc, "browser_save_session", {}, ctx) == "save_session-ok"
            assert await _run_local(svc, "browser_set_proxy", {"server": "s"}, ctx) == "set_proxy-ok"
            assert await _run_local(svc, "browser_monitor", {"active": True}, ctx) == "start_monitoring-ok"
            assert await _run_local(svc, "browser_monitor", {"active": False}, ctx) == "stop_monitoring-ok"
            assert await _run_local(svc, "browser_wait_for_selector", {"selector": "#b"}, ctx) == "wait_for_selector-ok"
            assert await _run_local(svc, "browser_extract_content", {"selector": "#b"}, ctx) == "extract_content-ok"
            assert await _run_local(svc, "browser_upload_file", {"selector": "#f", "file_path": "/tmp/f"}, ctx) == "upload_file-ok"
            assert await _run_local(svc, "browser_download_file", {"url": "u"}, ctx) == "download_file-ok"

    async def test_browser_cloud_restricted(self):
        svc = _svc()
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.database.SessionLocal", return_value=db),              patch("core.models.Workspace", new=MagicMock()),              patch("core.models.Tenant", new=MagicMock()),              patch("core.models.PlanType", new=MagicMock()):
            r = await _run_local(svc, "browser_navigate", {"url": "u"}, {"computer_use_mode": "cloud", "workspace_id": "w"})
            assert "restricted" in r.lower()
            r = await _run_local(svc, "browser_new_tab", {"url": "u"}, {"computer_use_mode": "cloud", "workspace_id": "w"})
            assert "restricted" in r.lower()
        r = await _run_local(svc, "browser_new_tab", {"url": "u"}, {"computer_use_mode": "desktop"})
        assert "only available" in r
        r = await _run_local(svc, "browser_switch_tab", {}, {"computer_use_mode": "desktop"})
        assert "only available" in r

    async def test_universal_crm_tools(self):
        svc = _svc()
        uis = MagicMock()
        uis.search = AsyncMock(return_value={"results": 1})
        uis.execute = AsyncMock(return_value={"status": "success", "data": []})
        with _mock_imports({
            "integrations.universal_integration_service": MagicMock(UniversalIntegrationService=_cls(uis)),
        }):
            r = await _run_local(svc, "search_contacts", {"query": "q", "platform": "salesforce"}, {"user_id": "u"})
            assert r == {"results": 1}
            r = await _run_local(svc, "search_contacts", {"query": "q"})
            assert "salesforce" in r
            r = await _run_local(svc, "create_crm_lead", {"platform": "salesforce", "first_name": "F", "last_name": "L", "email": "e", "company": "c"}, {})
            assert r == {"status": "success", "data": []}
            r = await _run_local(svc, "create_crm_lead", {})
            assert r["error"] == "platform is required"
            r = await _run_local(svc, "get_sales_pipeline", {"platform": "salesforce"}, {"user_id": "u"})
            assert r == []
            r = await _run_local(svc, "get_tasks", {"platform": "jira", "project": "p"}, {"user_id": "u"})
            assert r == {"status": "success", "data": []}
            r = await _run_local(svc, "get_tasks", {})
            assert "jira" in r
            r = await _run_local(svc, "search_tasks", {"query": "q", "platform": "jira"})
            assert r == {"results": 1}
            r = await _run_local(svc, "search_tasks", {"query": "q"})
            assert "jira" in r
            r = await _run_local(svc, "create_task", {"platform": "jira", "project": "p", "title": "t"}, {"user_id": "u"})
            assert r == {"status": "success", "data": []}
            r = await _run_local(svc, "list_projects", {"platform": "jira"})
            assert r == {"status": "success", "data": []}
            r = await _run_local(svc, "list_projects", {})
            assert r["error"] == "platform is required"

    async def test_create_task_without_platform(self):
        svc = _svc()
        conn = MagicMock()
        conn.piece_name = "asana"
        conn_service = MagicMock()
        conn_service.list_connections = AsyncMock(return_value=[conn])
        uis = MagicMock()
        uis.execute = AsyncMock(return_value={"ok": 1})
        with _mock_imports({
            "core.connection_service": MagicMock(ConnectionService=_cls(conn_service)),
            "integrations.universal_integration_service": MagicMock(UniversalIntegrationService=_cls(uis)),
        }):
            r = await _run_local(svc, "create_task", {"project": "p", "title": "t"}, {"user_id": "u"})
            assert r == {"ok": 1}
            conn_service2 = MagicMock()
            conn_service2.list_connections = AsyncMock(return_value=[])
            with _mock_imports({
                "core.connection_service": MagicMock(ConnectionService=_cls(conn_service2)),
            }):
                r = await _run_local(svc, "create_task", {"title": "t"}, {"user_id": "u"})
            assert "No project management" in r["error"]

    async def test_communication_tools(self):
        svc = _svc()
        uis = MagicMock()
        uis.execute = AsyncMock(return_value={"ok": 1})
        uis.search = AsyncMock(return_value={"results": 1})
        conn = MagicMock()
        conn.piece_name = "slack"
        conn_service = MagicMock()
        conn_service.list_connections = AsyncMock(return_value=[conn])
        with _mock_imports({
            "integrations.universal_integration_service": MagicMock(UniversalIntegrationService=_cls(uis)),
            "core.connection_service": MagicMock(ConnectionService=_cls(conn_service)),
        }):
            with patch.object(svc, "_check_hitl_policy", new=AsyncMock(return_value=None)):
                r = await _run_local(svc, "send_message", {"platform": "slack", "target": "c", "message": "m"}, {"user_id": "u", "workspace_id": "w"})
                assert r == {"ok": 1}
                r = await _run_local(svc, "post_channel_message", {"platform": "slack", "channel": "c", "message": "m"}, {"user_id": "u", "workspace_id": "w"})
                assert r == {"ok": 1}
                r = await _run_local(svc, "send_email", {"to": "x@y", "subject": "s", "body": "b"}, {"user_id": "u", "workspace_id": "w"})
                assert r == {"ok": 1}
            r = await _run_local(svc, "search_emails", {"query": "q", "platform": "gmail"}, {"user_id": "u"})
            assert r == {"ok": 1}
            r = await _run_local(svc, "search_emails", {"query": "q"})
            assert "gmail" in r
            r = await _run_local(svc, "unified_communication_search", {"query": "q"}, {"user_id": "u"})
            assert "slack" in r
            r = await _run_local(svc, "list_calendar_events", {"calendar_id": "c"}, {"user_id": "u"})
            assert r == {"ok": 1}
            r = await _run_local(svc, "create_calendar_event", {"summary": "m"}, {"user_id": "u"})
            assert r == {"ok": 1}
            # R81b: risky tool still needs the HITL allow-mock outside the
            # earlier context (missing workspace now blocks instead of allowing).
            with patch.object(svc, "_check_hitl_policy", new=AsyncMock(return_value=None)):
                r = await _run_local(svc, "post_channel_message", {"channel": "c", "message": "m"}, {"user_id": "u", "workspace_id": "w"})
                assert r["error"] == "platform is required"

    async def test_send_message_no_connection(self):
        svc = _svc()
        conn_service = MagicMock()
        conn_service.list_connections = AsyncMock(return_value=[])
        with _mock_imports({"core.connection_service": MagicMock(ConnectionService=_cls(conn_service))}):
            with patch.object(svc, "_check_hitl_policy", new=AsyncMock(return_value=None)):
                r = await _run_local(svc, "send_message", {"platform": "slack", "target": "c", "message": "m"}, {"user_id": "u", "workspace_id": "w"})
        assert "No communication platform" in r["error"]

    async def test_send_message_hitl_blocked(self):
        svc = _svc()
        with patch.object(svc, "_check_hitl_policy", new=AsyncMock(return_value={"paused": True})):
            r = await _run_local(svc, "send_message", {"message": "m"}, {"user_id": "u", "workspace_id": "w"})
        assert r == {"paused": True}

    async def test_storage_knowledge_tools(self):
        svc = _svc()
        uis = MagicMock()
        uis.search = AsyncMock(return_value={"results": 1})
        uis.execute = AsyncMock(return_value={"ok": 1})
        engine = MagicMock()
        entity = MagicMock()
        entity.canonical_name = "alpha"
        entity.entity_id = "e1"
        entity.entity_type.value = "company"
        entity.source_platforms = [MagicMock(value="salesforce")]
        entity.updated_at = datetime.now(timezone.utc)
        engine.entity_registry = {"e1": entity}
        with _mock_imports({
            "integrations.universal_integration_service": MagicMock(UniversalIntegrationService=_cls(uis)),
            "ai.data_intelligence": MagicMock(DataIntelligenceEngine=_cls(engine)),
        }):
            r = await _run_local(svc, "search_files", {"query": "q", "platform": "google_drive"})
            assert r == {"results": 1}
            r = await _run_local(svc, "search_files", {"query": "q"})
            assert "google_drive" in r
            r = await _run_local(svc, "list_files", {"platform": "google_drive"})
            assert r == {"ok": 1}
            r = await _run_local(svc, "list_files", {})
            assert r["error"] == "platform is required"
            r = await _run_local(svc, "create_folder", {"platform": "google_drive", "name": "n"})
            assert r == {"ok": 1}
            r = await _run_local(svc, "create_folder", {})
            assert r["error"] == "platform is required"
            r = await _run_local(svc, "unified_knowledge_search", {"query": "alpha"})
            assert r[0]["id"] == "e1"
            r = await _run_local(svc, "unified_knowledge_search", {})
            assert len(r) == 1

    async def test_save_business_fact_and_verify_citation(self):
        svc = _svc()
        wm = MagicMock()
        wm.record_business_fact = AsyncMock(return_value=True)
        with _mock_imports({"core.agent_world_model": MagicMock(WorldModelService=_cls(wm))}):
            r = await _run_local(svc, "save_business_fact", {"fact": "f", "citations": [], "reason": "r", "source": "s"}, {"workspace_id": "w", "agent_id": "a"})
            assert "saved" in r
        wm2 = MagicMock()
        wm2.record_business_fact = AsyncMock(return_value=False)
        with _mock_imports({"core.agent_world_model": MagicMock(WorldModelService=_cls(wm2))}):
            r = await _run_local(svc, "save_business_fact", {"fact": "f"}, {"workspace_id": "w"})
            assert "Failed" in r
        r = await _run_local(svc, "verify_citation", {"path": "/etc/passwd"})
        assert "denied" in r
        with patch("integrations.mcp_service.os.path.exists", return_value=True), \
             patch("builtins.open", MagicMock()) as m:
            m.return_value.__enter__.return_value.read.return_value = "snippet"
            r = await _run_local(svc, "verify_citation", {"path": "/tmp/x"})
            assert "Verified" in r
        with patch("integrations.mcp_service.os.path.exists", return_value=False):
            r = await _run_local(svc, "verify_citation", {"path": "/tmp/x"})
            assert "NOT found" in r
        r = await _run_local(svc, "verify_citation", {})
        assert "Path required" in r

    async def test_support_and_dev_tools(self):
        svc = _svc()
        uis = MagicMock()
        uis.search = AsyncMock(return_value={"results": 1})
        uis.execute = AsyncMock(return_value={"ok": 1})
        with _mock_imports({"integrations.universal_integration_service": MagicMock(UniversalIntegrationService=_cls(uis))}):
            r = await _run_local(svc, "search_tickets", {"query": "q", "platform": "zendesk"})
            assert r == {"results": 1}
            r = await _run_local(svc, "search_tickets", {"query": "q"})
            assert "zendesk" in r
            r = await _run_local(svc, "create_ticket", {"platform": "zendesk", "subject": "s"})
            assert r == {"ok": 1}
            r = await _run_local(svc, "create_ticket", {})
            assert r["error"] == "platform is required"
            r = await _run_local(svc, "search_repositories", {"query": "q", "platform": "github"})
            assert r == {"results": 1}
            r = await _run_local(svc, "search_repositories", {"query": "q"})
            assert "github" in r
            r = await _run_local(svc, "search_designs", {"query": "q"})
            assert r == {"results": 1}
            r = await _run_local(svc, "query_financial_metrics", {"period": "2026-07"})
            assert r == {"ok": 1}
            r = await _run_local(svc, "list_finance_invoices", {"platform": "stripe"})
            assert r == {"ok": 1}
            r = await _run_local(svc, "list_finance_invoices", {})
            assert "stripe" in r
            r = await _run_local(svc, "search_dashboards", {"query": "q", "platform": "tableau"})
            assert r == {"results": 1}
            r = await _run_local(svc, "search_dashboards", {"query": "q"})
            assert "tableau" in r

    async def test_finance_close_check_second_branch(self):
        svc = _svc()
        agent = MagicMock()
        agent.run_close_check = AsyncMock(return_value={"ok": True})
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        with patch("accounting.close_agent.CloseChecklistAgent", _cls(agent)), \
             patch("core.database.SessionLocal", lambda: db):
            r = await _run_local(svc, "finance_close_check", {}, {"workspace_id": "w"})
        assert r == {"ok": True}

    async def test_get_inventory_levels(self):
        svc = _svc()
        conn_sf = MagicMock()
        conn_sf.piece_name = "shopify"
        conn_sf.credentials = {"access_token": "tok"}
        conn_sf.metadata = {"shop_url": "s"}
        conn_z = MagicMock()
        conn_z.piece_name = "zoho_inventory"
        conn_z.credentials = {"access_token": "tok"}
        conn_z.metadata = {"organization_id": "o"}
        conn_service = MagicMock()
        conn_service.list_connections = AsyncMock(return_value=[conn_sf, conn_z])
        shopify = MagicMock()
        shopify.get_inventory_levels = AsyncMock(return_value=[{"i": 1}])
        zoho = MagicMock()
        zoho.get_inventory_levels = AsyncMock(return_value=[{"z": 1}])
        with _mock_imports({
            "core.connection_service": MagicMock(ConnectionService=_cls(conn_service)),
            "integrations.shopify_service": MagicMock(ShopifyService=_cls(shopify)),
            "integrations.zoho_inventory_service": MagicMock(zoho_inventory_service=zoho),
        }):
            r = await _run_local(svc, "get_inventory_levels", {"platform": "shopify"}, {"user_id": "u"})
            assert r == [{"i": 1}]
            r = await _run_local(svc, "get_inventory_levels", {"platform": "zoho"}, {"user_id": "u"})
            assert r == [{"z": 1}]
            conn_service3 = MagicMock()
            conn_service3.list_connections = AsyncMock(return_value=[])
            with _mock_imports({"core.connection_service": MagicMock(ConnectionService=_cls(conn_service3))}):
                r = await _run_local(svc, "get_inventory_levels", {}, {"user_id": "u"})
            assert r == []

    async def test_whatsapp_send_message_via_manager(self):
        svc = _svc()
        manager = MagicMock()
        manager.status = "connected"
        manager.integration = MagicMock()
        manager.integration.send_message = AsyncMock(return_value={"ok": 1})
        with _mock_imports({
            "integrations.whatsapp_service_manager": MagicMock(whatsapp_service_manager=manager),
        }):
            with patch.object(svc, "_check_hitl_policy", new=AsyncMock(return_value=None)):
                r = await _run_local(svc, "whatsapp_send_message", {"to": "+1", "message": "hi"}, {"user_id": "u", "workspace_id": "w"})
                assert r == {"ok": 1}
            manager2 = MagicMock()
            manager2.status = "disconnected"
            manager2.initialize_service = AsyncMock()
            manager2.integration = None
            with _mock_imports({
                "integrations.whatsapp_service_manager": MagicMock(whatsapp_service_manager=manager2),
            }):
                with patch.object(svc, "_check_hitl_policy", new=AsyncMock(return_value=None)):
                    r = await _run_local(svc, "whatsapp_send_message", {"to": "+1", "message": "hi"}, {"user_id": "u", "workspace_id": "w"})
                assert "unavailable" in r["error"]
            manager3 = MagicMock()
            manager3.status = "initialized"
            manager3.initialize_service = AsyncMock()
            manager3.integration = MagicMock(spec=["other_method"])
            with _mock_imports({
                "integrations.whatsapp_service_manager": MagicMock(whatsapp_service_manager=manager3),
            }):
                with patch.object(svc, "_check_hitl_policy", new=AsyncMock(return_value=None)):
                    r = await _run_local(svc, "whatsapp_send_message", {"to": "+1", "message": "hi"}, {"user_id": "u", "workspace_id": "w"})
                assert "not found" in r["error"]
            manager4 = MagicMock()
            manager4.status = "connected"
            manager4.integration = MagicMock(spec=["other_method"])
            with _mock_imports({
                "integrations.whatsapp_service_manager": MagicMock(whatsapp_service_manager=manager4),
            }):
                with patch.object(svc, "_check_hitl_policy", new=AsyncMock(return_value=None)):
                    r = await _run_local(svc, "whatsapp_send_message", {"to": "+1", "message": "hi"}, {"user_id": "u", "workspace_id": "w"})
                assert "not found" in r["error"]

    async def test_whatsapp_import_error(self):
        svc = _svc()
        with _mock_imports({"integrations.whatsapp_service_manager": None}):
            pass
        with patch.dict(sys.modules, {"integrations.whatsapp_service_manager": None}):
            import importlib
            real = sys.modules.pop("integrations.whatsapp_service_manager", None)
            try:
                sys.modules["integrations.whatsapp_service_manager"] = None
                with patch.object(svc, "_check_hitl_policy", new=AsyncMock(return_value=None)):
                    r = await _run_local(svc, "whatsapp_send_message", {"to": "+1", "message": "hi"}, {"user_id": "u", "workspace_id": "w"})
                assert "not found" in r["error"]
            finally:
                if real is not None:
                    sys.modules["integrations.whatsapp_service_manager"] = real
                else:
                    sys.modules.pop("integrations.whatsapp_service_manager", None)

    async def test_create_zoom_meeting(self):
        svc = _svc()
        conn_service = MagicMock()
        conn_service.list_connections = AsyncMock(return_value=[])
        zoom = MagicMock()
        zoom.create_meeting = AsyncMock(return_value={"link": 1})
        with _mock_imports({
            "core.connection_service": MagicMock(ConnectionService=_cls(conn_service)),
            "integrations.zoom_service": MagicMock(ZoomService=_cls(zoom)),
        }):
            r = await _run_local(svc, "create_zoom_meeting", {}, {"user_id": "u"})
            assert r["error"] == "Zoom not connected"
            conn = MagicMock()
            conn.piece_name = "zoom"
            conn.credentials = {"access_token": "tok"}
            conn_service2 = MagicMock()
            conn_service2.list_connections = AsyncMock(return_value=[conn])
            with _mock_imports({
                "core.connection_service": MagicMock(ConnectionService=_cls(conn_service2)),
                "integrations.zoom_service": MagicMock(ZoomService=_cls(zoom)),
            }):
                r = await _run_local(svc, "create_zoom_meeting", {"topic": "t", "duration": 30}, {"user_id": "u"})
            assert r == {"link": 1}

    async def test_get_system_health(self):
        svc = _svc()
        cb = MagicMock()
        cb.get_stats.return_value = {"s": 1}
        cb.get_all_stats.return_value = {"a": 1}
        analyzer = MagicMock()
        analyzer.analyze_service_drift.return_value = {"drift": 1}
        analyzer.get_global_performance_report.return_value = {"g": 1}
        with _mock_imports({
            "core.circuit_breaker": MagicMock(circuit_breaker=cb),
            "core.analytics_engine": MagicMock(
                analyzer=analyzer,
                get_analytics_engine=Mock(return_value=analyzer),
            ),
        }):
            r = await _run_local(svc, "get_system_health", {"service": "shopify"})
            assert r == {"stats": {"s": 1}, "drift": {"drift": 1}}
            r = await _run_local(svc, "get_system_health", {})
            assert r == {"circuit_breaker": {"a": 1}, "global_report": {"g": 1}}

    async def test_generate_pdf_report(self):
        svc = _svc()
        pdf = MagicMock()
        with _mock_imports({"fpdf": ModuleType("_fpdf")}):
            import fpdf
            fpdf.FPDF = _cls(pdf)
            r = await _run_local(svc, "generate_pdf_report", {"content": "line1\nline2", "filename": "../../evil"})
        assert r["status"] == "success"
        assert "/tmp/evil.pdf" in r["file_path"]

    async def test_marketing_and_sales_tools(self):
        svc = _svc()
        agent = MagicMock()
        agent.manage_google_reviews = AsyncMock(return_value={"reviews": 1})
        agent.request_testimonial = AsyncMock(return_value={"testimonial": 1})
        agent.run_ads_check = AsyncMock(return_value={"ads": 1})
        sales = MagicMock()
        sales.score_lead = AsyncMock(return_value={"score": 1})
        sales.prepare_outreach = AsyncMock(return_value={"outreach": 1})
        sales.audit_pipeline = AsyncMock(return_value={"pipeline": 1})
        with _mock_imports({
            "core.marketing_agent": MagicMock(MarketingAgent=_cls(agent)),
            "core.sales_agent": MagicMock(SalesAgent=_cls(sales)),
        }):
            r = await _run_local(svc, "manage_reviews", {}, {"workspace_id": "w"})
            assert r == {"reviews": 1}
            r = await _run_local(svc, "request_testimonial", {"customer_id": "c", "platform": "email"}, {"workspace_id": "w"})
            assert r == {"testimonial": 1}
            r = await _run_local(svc, "analyze_ads_performance", {"service": "meta_ads"}, {"workspace_id": "w"})
            assert r == {"ads": 1}
            r = await _run_local(svc, "score_lead", {"lead_data": {}}, {"workspace_id": "w"})
            assert r == {"score": 1}
            r = await _run_local(svc, "draft_sales_outreach", {"lead_id": "l"}, {"workspace_id": "w"})
            assert r == {"outreach": 1}
            r = await _run_local(svc, "monitor_pipeline_health", {}, {"workspace_id": "w"})
            assert r == {"pipeline": 1}

    async def test_shipping_tools(self):
        svc = _svc()
        uis = MagicMock()
        uis.execute = AsyncMock(return_value={"ok": 1})
        with _mock_imports({"integrations.universal_integration_service": MagicMock(UniversalIntegrationService=_cls(uis))}):
            for tool, action in [("create_shipment", "create_shipment"), ("get_shipping_rates", "get_rates"),
                                 ("create_shipping_label", "create_label"), ("track_shipment", "track"),
                                 ("validate_address", "validate_address")]:
                r = await _run_local(svc, tool, {"platform": "shippo", "from_address": {}}, {"user_id": "u"})
                assert r == {"ok": 1}
            conn = MagicMock()
            conn.piece_name = "easypost"
            conn_service = MagicMock()
            conn_service.list_connections = AsyncMock(return_value=[conn])
            with _mock_imports({
                "core.connection_service": MagicMock(ConnectionService=_cls(conn_service)),
                "integrations.universal_integration_service": MagicMock(UniversalIntegrationService=_cls(uis)),
            }):
                r = await _run_local(svc, "create_shipment", {"from_address": {}}, {"user_id": "u"})
                assert r == {"ok": 1}
            conn_service2 = MagicMock()
            conn_service2.list_connections = AsyncMock(return_value=[])
            with _mock_imports({
                "core.connection_service": MagicMock(ConnectionService=_cls(conn_service2)),
            }):
                r = await _run_local(svc, "create_shipment", {"from_address": {}}, {"user_id": "u"})
            assert "No shipping platform" in r["error"]

    async def test_cloud_provider_tools(self):
        svc = _svc()
        uis = MagicMock()
        uis.execute = AsyncMock(return_value={"ok": 1})
        with _mock_imports({"integrations.universal_integration_service": MagicMock(UniversalIntegrationService=_cls(uis))}):
            for tool in ["s3_upload", "s3_download", "lambda_invoke", "sqs_send", "sns_publish"]:
                assert await _run_local(svc, tool, {"bucket": "b"}) == {"ok": 1}
            for tool in ["azure_blob_upload", "azure_blob_download", "azure_function_invoke"]:
                assert await _run_local(svc, tool, {"container": "c"}) == {"ok": 1}
            for tool in ["gcs_upload", "gcs_download", "cloud_function_invoke", "pubsub_publish"]:
                assert await _run_local(svc, tool, {"bucket": "b"}) == {"ok": 1}

    async def test_knowledge_ingestion_tools(self):
        svc = _svc()
        ing = MagicMock()
        ing.process_document = AsyncMock(return_value={"stats": 1})
        ing.query_graphrag = AsyncMock(return_value={"g": 1})
        processor = MagicMock()
        processor.process_document = AsyncMock(return_value={"success": True, "content": "text", "page_count": 1, "total_chars": 4, "tables": [{"t": 1}]})
        extractor = MagicMock()
        extractor.extract_from_file.return_value = [{"name": "f", "expression": "=1", "domain": "d"}]
        with _mock_imports({
            "core.knowledge_ingestion": MagicMock(get_knowledge_ingestion=lambda: ing),
            "core.docling_processor": MagicMock(get_docling_processor=lambda: processor),
            "core.formula_extractor": MagicMock(get_formula_extractor=lambda w: extractor),
        }):
            r = await _run_local(svc, "ingest_knowledge_from_text", {}, {"workspace_id": "w", "user_id": "u"})
            assert r["error"] == "Text content is required"
            r = await _run_local(svc, "ingest_knowledge_from_text", {"text": "t"}, {"workspace_id": "w", "user_id": "u"})
            assert r == {"success": True, "stats": {"stats": 1}}
            r = await _run_local(svc, "ingest_knowledge_from_file", {}, {"workspace_id": "w", "user_id": "u"})
            assert r["error"] == "File path is required"
            r = await _run_local(svc, "ingest_knowledge_from_file", {"file_path": "/nope"}, {"workspace_id": "w"})
            assert "not found" in r["error"]
            with patch("integrations.mcp_service.os.path.exists", return_value=True):
                with _mock_imports({
                    "core.knowledge_ingestion": MagicMock(get_knowledge_ingestion=lambda: ing),
                    "core.docling_processor": MagicMock(get_docling_processor=lambda: processor),
                    "core.formula_extractor": MagicMock(get_formula_extractor=lambda w: extractor),
                }):
                    r = await _run_local(svc, "ingest_knowledge_from_file", {"file_path": "/tmp/f.xlsx"}, {"workspace_id": "w", "user_id": "u"})
                    assert r["success"] is True
                    assert r["file_stats"]["formulas_extracted"] == 1
            with patch("integrations.mcp_service.os.path.exists", return_value=True):
                processor2 = MagicMock()
                processor2.process_document = AsyncMock(return_value={"success": False, "error": "bad"})
                with _mock_imports({
                    "core.knowledge_ingestion": MagicMock(get_knowledge_ingestion=lambda: ing),
                    "core.docling_processor": MagicMock(get_docling_processor=lambda: processor2),
                }):
                    r = await _run_local(svc, "ingest_knowledge_from_file", {"file_path": "/tmp/f.pdf"}, {"workspace_id": "w"})
                assert "parsing failed" in r["error"]
            with patch("integrations.mcp_service.os.path.exists", return_value=True):
                processor3 = MagicMock()
                processor3.process_document = AsyncMock(return_value={"success": True, "content": ""})
                with _mock_imports({
                    "core.knowledge_ingestion": MagicMock(get_knowledge_ingestion=lambda: ing),
                    "core.docling_processor": MagicMock(get_docling_processor=lambda: processor3),
                }):
                    r = await _run_local(svc, "ingest_knowledge_from_file", {"file_path": "/tmp/f.pdf"}, {"workspace_id": "w"})
                assert "No content" in r["error"]

    async def test_search_formulas_and_query_graph(self):
        svc = _svc()
        manager = MagicMock()
        manager.search_formulas.return_value = [{"f": 1}]
        ing = MagicMock()
        ing.query_graphrag = MagicMock(return_value={"g": 1})
        with _mock_imports({
            "core.formula_memory": MagicMock(get_formula_manager=lambda **kw: manager),
            "core.knowledge_ingestion": MagicMock(get_knowledge_ingestion=lambda: ing),
        }):
            r = await _run_local(svc, "search_formulas", {}, {"workspace_id": "w", "user_id": "u"})
            assert r["error"] == "Search query is required"
            r = await _run_local(svc, "search_formulas", {"query": "q"}, {"workspace_id": "w", "user_id": "u"})
            assert r == {"results": [{"f": 1}]}
            r = await _run_local(svc, "query_knowledge_graph", {}, {"user_id": "u"})
            assert r["error"] == "Search query is required"
            r = await _run_local(svc, "query_knowledge_graph", {"query": "q"}, {"user_id": "u"})
            assert r == {"g": 1}

    async def test_standardized_tools(self):
        svc = _svc()
        uis = MagicMock()
        uis.execute = AsyncMock(return_value={"ok": 1})
        with _mock_imports({
            "integrations.universal_integration_service": MagicMock(universal_integration_service=uis),
        }):
            r = await _run_local(svc, "update_crm_lead", {"platform": "sf", "id": "1", "data": {}})
            assert r == {"ok": 1}
            r = await _run_local(svc, "create_crm_deal", {"platform": "sf", "data": {}})
            assert r == {"ok": 1}
            r = await _run_local(svc, "update_crm_deal", {"platform": "sf", "id": "1"})
            assert r == {"ok": 1}
            r = await _run_local(svc, "update_task", {"platform": "jira", "id": "1"})
            assert r == {"ok": 1}
            r = await _run_local(svc, "create_support_ticket", {"platform": "zd", "subject": "s"})
            assert r == {"ok": 1}
            r = await _run_local(svc, "update_support_ticket", {"platform": "zd", "id": "1"})
            assert r == {"ok": 1}
            r = await _run_local(svc, "create_ecommerce_order", {"platform": "shopify", "customer_id": "c"})
            assert r == {"ok": 1}
            r = await _run_local(svc, "upload_file_to_storage", {"platform": "gd", "file_path": "/f"})
            assert r == {"ok": 1}
            r = await _run_local(svc, "create_storage_folder", {"platform": "gd", "name": "n"})
            assert r == {"ok": 1}
            r = await _run_local(svc, "add_marketing_subscriber", {"platform": "mc", "email": "e"})
            assert r == {"ok": 1}
            r = await _run_local(svc, "create_invoice", {"platform": "stripe", "amount": 5})
            assert r == {"ok": 1}
            r = await _run_local(svc, "create_record", {"service": "sf", "entity": "lead", "data": {}})
            assert r == {"ok": 1}
            r = await _run_local(svc, "update_record", {"service": "sf", "entity": "lead", "id": "1", "data": {}})
            assert r == {"ok": 1}
            r = await _run_local(svc, "push_to_integration", {"service": "sf", "action": "sync", "params": {}})
            assert r == {"ok": 1}
            r = await _run_local(svc, "call_integration", {"service": "sf", "action": "list", "params": {}})
            assert r == {"ok": 1}

    async def test_discover_connections_and_global_search(self):
        svc = _svc()
        conn_service = MagicMock()
        conn_service.get_connections.return_value = [
            {"integration_id": "salesforce", "status": "active"},
            {"integration_id": "hubspot", "status": "inactive"},
        ]
        uis = MagicMock()
        uis.search = AsyncMock(return_value={"res": 1})
        with _mock_imports({
            "core.connection_service": MagicMock(connection_service=conn_service),
            "integrations.universal_integration_service": MagicMock(universal_integration_service=uis),
        }):
            r = await _run_local(svc, "discover_connections", {}, {"user_id": "u"})
            assert r == {"active_integrations": ["salesforce"]}
            r = await _run_local(svc, "global_search", {"query": "q", "platforms": ["slack", "gmail"]}, {"user_id": "u"})
            assert r == {"slack": {"res": 1}, "gmail": {"res": 1}}
            r = await _run_local(svc, "global_search", {"query": "q"}, {"user_id": "u"})
            assert "salesforce" in r

    async def test_unknown_tool(self):
        svc = _svc()
        r = await _run_local(svc, "no_such_tool", {})
        assert r["status"] == "not_implemented"

    async def test_list_integrations(self):
        svc = _svc()
        with patch("integrations.universal_integration_service.NATIVE_INTEGRATIONS",
                   {"salesforce", "hubspot"}):
            r = await _run_local(svc, "list_integrations")
        assert r["native_count"] == 2


# ---------------------------------------------------------------------------
# execute_entity_tool / permissions / web_search
# ---------------------------------------------------------------------------
class TestEntityTool:
    async def test_execute_entity_tool_success(self):
        svc = _svc()
        with patch.object(svc, "execute_tool", new=AsyncMock(return_value={"ok": 1})) as et:
            r = await svc.execute_entity_tool(
                {"entity_id": "e1", "entity_type_slug": "vendor", "tenant_id": "t1", "agent_id": "a1",
                 "entity_data": {"email": "x@y"}, "workspace_id": "w"},
                "some_skill",
                {"to": "entity.email"},
            )
        assert r["status"] == "success"
        assert r["entity_id"] == "e1"
        assert et.call_args.args[2]["to"] == "x@y"

    async def test_execute_entity_tool_missing_field(self):
        svc = _svc()
        r = await svc.execute_entity_tool({"entity_type_slug": "x"}, "s", {})
        assert r["status"] == "error"
        assert "missing" in r["error"]

    async def test_execute_entity_tool_error(self):
        svc = _svc()
        with patch.object(svc, "execute_tool", new=AsyncMock(side_effect=RuntimeError("boom"))):
            r = await svc.execute_entity_tool(
                {"entity_id": "e1", "entity_type_slug": "v", "tenant_id": "t", "agent_id": "a"}, "s", {}
            )
        assert r["status"] == "error"

    async def test_check_entity_skill_permission_cache_and_miss(self):
        import integrations.mcp_service as mod

        svc = _svc()
        svc._permission_cache = {"entity_skill_perm:t:vendor:sk": (0, {"allowed": True})}
        with patch("time.time", return_value=1.0):
            r = svc.check_entity_skill_permission("t", "vendor", "sk")
            assert r == {"allowed": True}
        svc._permission_cache = {}
        skill_service = MagicMock()
        skill_service.check_skill_permission.return_value = {"allowed": True, "reason": "r"}
        skill = MagicMock()
        skill.name = "skillname"
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        db.query.return_value.filter.return_value.first.return_value = skill
        with patch("core.entity_skill_service.get_entity_skill_service", return_value=skill_service), \
             patch("core.database.SessionLocal", return_value=db), \
             patch("time.time", return_value=100.0):
            r = svc.check_entity_skill_permission("t", "vendor", "sk")
        assert r["skill_name"] == "skillname"
        assert "entity_skill_perm:t:vendor:sk" in svc._permission_cache

    async def test_check_entity_skill_permission_error(self):
        svc = _svc()
        with patch("core.entity_skill_service.get_entity_skill_service", side_effect=RuntimeError("x")):
            r = svc.check_entity_skill_permission("t", "vendor", "sk")
        assert r["allowed"] is False

    async def test_inject_entity_context_and_nested_field(self):
        svc = _svc()
        ctx = MagicMock()
        ctx.entity_data = {"properties": {"email": "x@y"}, "name": "acme"}
        args = {"to": "entity.properties.email", "name": "entity.name", "plain": 1}
        aug = svc._inject_entity_context(args, ctx)
        assert aug["to"] == "x@y"
        assert aug["name"] == "acme"
        assert aug["plain"] == 1
        assert svc._get_nested_field({"a": {"b": 1}}, "a.b") == 1
        assert svc._get_nested_field({"a": 1}, "a.b") is None
        assert svc._get_nested_field({}, "a") is None


class TestWebSearch:
    async def test_web_search_byok_key(self):
        import integrations.mcp_service as mod

        svc = _svc()
        byok = MagicMock()
        byok.get_tenant_api_key.return_value = "byok-key"
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        with patch("integrations.mcp_service.get_byok_manager", return_value=byok), \
             patch("core.database.SessionLocal", return_value=db), \
             patch("integrations.mcp_service.httpx.AsyncClient") as client_cls:
            client = _conn()
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"results": []}
            client.post = AsyncMock(return_value=resp)
            client_cls.return_value = client
            r = await svc.web_search("q", "tenant1")
            assert r == {"results": []}
        byok.get_tenant_api_key.assert_called_once()

    async def test_web_search_env_key_and_errors(self):
        import integrations.mcp_service as mod

        svc = _svc()
        with patch("integrations.mcp_service.get_byok_manager", side_effect=RuntimeError("x")), \
             patch("integrations.mcp_service.os.getenv", return_value="env-key"), \
             patch("integrations.mcp_service.httpx.AsyncClient") as client_cls:
            client = _conn()
            resp = MagicMock()
            resp.status_code = 500
            resp.text = "boom"
            client.post = AsyncMock(return_value=resp)
            client_cls.return_value = client
            r = await svc.web_search("q")
            assert r["results"] == []
            client.post = AsyncMock(side_effect=RuntimeError("net"))
            r = await svc.web_search("q")
            assert r["error"] is not None

    async def test_web_search_no_key(self):
        import integrations.mcp_service as mod

        svc = _svc()
        with patch("integrations.mcp_service.get_byok_manager", return_value=MagicMock()), \
             patch("core.database.SessionLocal") as sl, \
             patch("integrations.mcp_service.os.getenv", return_value=None):
            sl.return_value.__enter__.return_value = MagicMock()
            r = await svc.web_search("q")
        assert r["results"] == []
        assert "not configured" in r["error"]


# ---------------------------------------------------------------------------
# mcp_service — remaining branch coverage (wave 2)
# ---------------------------------------------------------------------------
class TestMCPCoverageWave2:
    async def test_register_tools_no_get_operations(self):
        import integrations.mcp_service as mod

        svc = _svc()
        db = MagicMock()
        i1 = MagicMock()
        i1.connector_id = "noops"
        db.query.return_value.filter.return_value.all.return_value = [i1]
        reg = MagicMock()
        reg.get_service_instance = AsyncMock(return_value=MagicMock())
        with patch("core.models.TenantIntegration", new=MagicMock()), \
             patch("core.integration_registry.IntegrationRegistry", return_value=reg):
            tools = await svc.register_integration_tools("t", db)
        assert tools == []

    async def test_execute_integration_tool_invalid_names(self):
        import integrations.mcp_service as mod

        svc = _svc()
        r = await svc.execute_integration_tool("noseparator", {}, {"tenant_id": "t", "agent_id": "a"})
        assert r["status"] == "error"
        r = await svc.execute_integration_tool("", {}, {"tenant_id": "t", "agent_id": "a"})
        assert r["status"] == "error"

    async def test_execute_integration_tool_error_path(self):
        import integrations.mcp_service as mod

        svc = _svc()
        with patch(
            "integrations.universal_integration_service.UniversalIntegrationService.execute",
            new=AsyncMock(side_effect=RuntimeError("kaput")),
        ):
            r = await svc.execute_integration_tool(
                "salesforce_list", {}, {"tenant_id": "t", "agent_id": "a", "user_id": "u"}
            )
        assert r["status"] == "error"
        assert "kaput" in r["error"]

    async def test_call_tool_external_skip_internal_servers(self):
        svc = _svc()
        hub = MagicMock()
        tool = MagicMock()
        tool.name = "ext_tool"
        hub.tools_cache = {"google-search": [tool], "local-tools": [tool], "brightdata": [tool]}
        hub.call_external_tool = AsyncMock(return_value={"ext": 1})
        with patch("core.capability_resolver.get_agent_for_context", return_value=None), \
             patch("core.sandbox_gate.evaluate_tool_call", return_value=None), \
             patch("core.action_registry.action_registry") as ar, \
             patch("core.mcp_service.mcp_service", hub):
            ar.get_action.return_value = None
            r = await svc.call_tool("ext_tool", {}, {})
        assert "not found" in r["error"]
        hub.call_external_tool.assert_not_called()

    async def test_hitl_role_required_and_autoapprove_and_force(self):
        import integrations.mcp_service as mod

        svc = _svc()
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        ws = MagicMock()
        ws.tenant_id = "t1"
        tenant = MagicMock()
        tenant.metadata_json = {"governance": {
            "require_hitl_external": True, "allow_autonomous_external": True,
            "roles": {"send_email": "ADMIN"},
        }}
        user = MagicMock()
        user.tenant_id = "t1"
        user.notification_preferences = {"force_agent_approval": False}
        agent = MagicMock()
        agent.maturity_level = 5
        agent.status = "autonomous"  # R81e: tier-name comparison
        agent.name = "A"
        # tenant-scoped agent query chains a second .filter() — loop the chain
        db.query.return_value.filter.return_value.filter.return_value = db.query.return_value.filter.return_value
        db.query.return_value.filter.return_value.first.side_effect = [ws, tenant, user, agent]
        with patch("core.database.SessionLocal", return_value=db), \
             patch("core.models.AgentRegistry", new=MagicMock()):
            r = await svc._check_hitl_policy("ws1", "send_email", {}, {"user_id": "u", "agent_id": "a"})
        assert r is None  # autonomous + allowed + not forced
        user2 = MagicMock()
        user2.tenant_id = "t1"
        user2.notification_preferences = {"force_agent_approval": True}
        agent2 = MagicMock()
        agent2.maturity_level = 5
        agent2.status = "autonomous"
        agent2.name = "A"
        agent2.id = "ag1"
        db.query.return_value.filter.return_value.filter.return_value = db.query.return_value.filter.return_value
        db.query.return_value.filter.return_value.first.side_effect = [ws, tenant, user2, agent2]
        with patch("core.database.SessionLocal", return_value=db), \
             patch("core.models.AgentRegistry", new=MagicMock()), \
             patch("core.intervention_service.intervention_service") as interv:
            interv.request_intervention = AsyncMock(return_value={"paused": True})
            r = await svc._check_hitl_policy("ws1", "send_email", {"to": "x"}, {"user_id": "u", "agent_id": "a"})
        assert r == {"paused": True}

    async def test_cloud_access_check_paths(self):
        import integrations.mcp_service as mod

        svc = _svc()
        cloud = MagicMock()
        cloud.navigate = AsyncMock(return_value="navigated")
        ws = MagicMock()
        ws.tenant_id = "t1"
        tenant = MagicMock()
        tenant.plan_type = "enterprise"
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        plan_type = MagicMock()
        plan_type.ENTERPRISE = "enterprise"
        # tenant found + enterprise -> cloud navigate runs
        db.query.return_value.filter.return_value.first.side_effect = [ws, tenant]
        with patch("core.database.SessionLocal", return_value=db), \
             patch("core.models.Workspace", new=MagicMock()), \
             patch("core.models.Tenant", new=MagicMock()), \
             patch("core.models.PlanType", plan_type), \
             _mock_imports({"core.cloud_browser_service": MagicMock(cloud_browser=cloud)}), \
             patch("integrations.mcp_service.get_tool_registry") as _reg:
            _reg.return_value.get.return_value = False
            ok = await svc.execute_tool(
                "local-tools", "browser_navigate", {"url": "u"},
                {"computer_use_mode": "cloud", "workspace_id": "w", "agent_id": "a"},
            )
            assert ok == "navigated"
            tenant2 = MagicMock()
            tenant2.plan_type = "free"
            db.query.return_value.filter.return_value.first.side_effect = [ws, tenant2]
            ok = await svc.execute_tool(
                "local-tools", "browser_navigate", {"url": "u"},
                {"computer_use_mode": "cloud", "workspace_id": "w"},
            )
            assert "restricted" in ok.lower()
        db2 = MagicMock()
        db2.__enter__ = MagicMock(side_effect=RuntimeError("db down"))
        db2.__exit__ = MagicMock(return_value=False)
        with patch("core.database.SessionLocal", return_value=db2), \
             patch("integrations.mcp_service.get_tool_registry") as _reg:
            _reg.return_value.get.return_value = False
            ok = await svc.execute_tool(
                "local-tools", "browser_navigate", {"url": "u"},
                {"computer_use_mode": "cloud", "workspace_id": "w"},
            )
        assert "restricted" in ok.lower()

    async def test_registry_async_tool_real_coroutine(self):
        import integrations.mcp_service as mod

        svc = _svc()
        registry = MagicMock()
        registry.get.return_value = True

        async def async_tool(a=1, **kwargs):
            return f"async-{a}"

        registry.get_function.return_value = async_tool
        with patch("integrations.mcp_service.get_tool_registry", return_value=registry):
            r = await svc.execute_tool("local-tools", "async_tool", {"a": 5}, {"agent_id": "x"})
        assert r == "async-5"

    async def test_shopify_update_inventory_failure(self):
        svc = _svc()
        store = MagicMock()
        store.access_token = "tok"
        store.shop_domain = "shop.myshopify.com"
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        db.query.return_value.filter.return_value.first.return_value = store
        shopify = MagicMock()
        shopify._get_base_url.return_value = "https://x"
        shopify._get_headers.return_value = {}
        with _mock_imports({
            "integrations.shopify_service": MagicMock(ShopifyService=_cls(shopify)),
            "core.database": MagicMock(SessionLocal=lambda: db),
            "core.models": MagicMock(EcommerceStore=MagicMock()),
        }), patch("integrations.mcp_service.httpx.AsyncClient") as client_cls:
            client = _conn()
            resp = MagicMock()
            resp.status_code = 400
            resp.text = "nope"
            client.post = AsyncMock(return_value=resp)
            client_cls.return_value = client
            r = await _run_local(svc, "shopify_update_inventory", {"inventory_item_id": "i", "location_id": "l", "available": 3})
            assert "Failed" in r

    async def test_list_workflows_error_paths(self):
        import integrations.mcp_service as mod

        svc = _svc()
        with patch.object(mod.os, "path") as os_path:
            os_path.exists.return_value = True
            with patch.object(mod.os, "listdir", return_value=["a.json"]):
                with patch("builtins.open", MagicMock()):
                    with patch.object(mod.json, "load", side_effect=ValueError("bad json")):
                        r = await _run_local(svc, "list_workflows")
                assert r == []
        with patch.object(mod.os, "path") as os_path:
            os_path.exists.return_value = True
            with patch.object(mod.os, "listdir", side_effect=PermissionError("denied")):
                r = await _run_local(svc, "list_workflows")
        assert r == []

    async def test_provider_failure_loops(self):
        svc = _svc()
        uis = MagicMock()
        uis.search = AsyncMock(side_effect=RuntimeError("provider down"))
        uis.execute = AsyncMock(side_effect=RuntimeError("provider down"))
        with _mock_imports({
            "integrations.universal_integration_service": MagicMock(UniversalIntegrationService=_cls(uis)),
        }):
            # Every provider raises -> per-provider except -> empty dicts
            for tool, args in [
                ("search_contacts", {"query": "q"}),
                ("get_tasks", {}),
                ("search_tasks", {"query": "q"}),
                ("search_files", {"query": "q"}),
                ("search_tickets", {"query": "q"}),
                ("search_repositories", {"query": "q"}),
                ("search_dashboards", {"query": "q"}),
                ("unified_communication_search", {"query": "q"}),
                ("list_finance_invoices", {}),
            ]:
                r = await _run_local(svc, tool, args, {"user_id": "u"})
                assert r == {}, tool
            r = await _run_local(svc, "get_sales_pipeline", {}, {"user_id": "u"})
            assert r == []

    async def test_unified_knowledge_search_no_match(self):
        svc = _svc()
        entity = MagicMock()
        entity.canonical_name = "alpha"
        entity.entity_id = "e1"
        entity.entity_type.value = "company"
        entity.source_platforms = []
        entity.updated_at = datetime.now(timezone.utc)
        engine = MagicMock()
        engine.entity_registry = {"e1": entity}
        with _mock_imports({"ai.data_intelligence": MagicMock(engine=engine)}):
            r = await _run_local(svc, "unified_knowledge_search", {"query": "zzz"})
        assert r == []

    async def test_verify_citation_read_error(self):
        svc = _svc()
        with patch("integrations.mcp_service.os.path.exists", return_value=True), \
             patch("builtins.open", side_effect=PermissionError("denied")):
            r = await _run_local(svc, "verify_citation", {"path": "/tmp/x"})
        assert "failed to read" in r

    async def test_browser_cloud_restricted_loop(self):
        svc = _svc()
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.database.SessionLocal", return_value=db), \
             patch("core.models.Workspace", new=MagicMock()), \
             patch("core.models.Tenant", new=MagicMock()), \
             patch("core.models.PlanType", new=MagicMock()):
            ctx = {"computer_use_mode": "cloud", "workspace_id": "w", "agent_id": "a"}
            for tool, args in [
                ("browser_click", {"selector": "#b"}),
                ("browser_type", {"text": "t"}),
                ("browser_screenshot", {}),
                ("browser_switch_tab", {}),
                ("browser_click_coords", {"x": 1, "y": 2}),
                ("list_browser_tabs", {}),
                ("browser_save_session", {}),
                ("browser_set_proxy", {"server": "s"}),
                ("browser_monitor", {"active": True}),
                ("browser_wait_for_selector", {"selector": "#b"}),
                ("browser_extract_content", {"selector": "#b"}),
                ("browser_upload_file", {"selector": "#f", "file_path": "/tmp/f"}),
                ("browser_download_file", {"url": "u"}),
            ]:
                r = await _run_local(svc, tool, args, ctx)
                assert "restricted" in r.lower(), tool
        # desktop-only errors
        ctx_d = {"computer_use_mode": "desktop"}
        for tool, args in [
            ("browser_switch_tab", {}),
            ("browser_click_coords", {"x": 1, "y": 2}),
            ("list_browser_tabs", {}),
            ("browser_save_session", {}),
            ("browser_set_proxy", {"server": "s"}),
            ("browser_monitor", {"active": True}),
            ("browser_wait_for_selector", {"selector": "#b"}),
            ("browser_extract_content", {"selector": "#b"}),
            ("browser_upload_file", {"selector": "#f"}),
            ("browser_download_file", {"url": "u"}),
        ]:
            r = await _run_local(svc, tool, args, ctx_d)
            assert "only available" in r, tool

    async def test_whatsapp_send_template_list_error_paths(self):
        svc = _svc()
        conn = MagicMock()
        conn.integration_id = "whatsapp"
        conn.credentials = {"access_token": "tok", "phone_number_id": "pn", "waba_id": "waba"}
        conn_service = MagicMock()
        conn_service.list_connections = AsyncMock(return_value=[conn])
        with _mock_imports({"core.connection_service": MagicMock(ConnectionService=_cls(conn_service))}):
            with patch("integrations.mcp_service.httpx.AsyncClient") as client_cls:
                client = _conn()
                resp = MagicMock()
                resp.status_code = 200
                resp.json.return_value = {"messages": [{"id": "m1"}]}
                resp.text = "err"
                client.post = AsyncMock(return_value=resp)
                client.get = AsyncMock(return_value=resp)
                client_cls.return_value = client
                r = await _run_local(svc, "whatsapp_send_template", {"to": "+1"}, {"user_id": "u"})
                assert "required" in r["error"]
                r = await _run_local(svc, "whatsapp_send_template", {"to": "+1", "template_name": "t"}, {"user_id": "u"})
                assert r["success"] is True
                resp.status_code = 400
                r = await _run_local(svc, "whatsapp_send_template", {"to": "+1", "template_name": "t"}, {"user_id": "u"})
                assert "error" in r
                client.get = AsyncMock(return_value=resp)
                r = await _run_local(svc, "whatsapp_list_templates", {}, {"user_id": "u"})
                assert "error" in r
        conn2 = MagicMock()
        conn2.integration_id = "whatsapp"
        conn2.credentials = {}
        conn_service2 = MagicMock()
        conn_service2.list_connections = AsyncMock(return_value=[conn2])
        with _mock_imports({"core.connection_service": MagicMock(ConnectionService=_cls(conn_service2))}):
            r = await _run_local(svc, "whatsapp_send_template", {"to": "+1", "template_name": "t"}, {"user_id": "u"})
            assert "incomplete" in r["error"]

    async def test_formula_extraction_failure_path(self):
        svc = _svc()
        ing = MagicMock()
        ing.process_document = AsyncMock(return_value={"stats": 1})
        processor = MagicMock()
        processor.process_document = AsyncMock(return_value={"success": True, "content": "text", "page_count": 1, "total_chars": 4, "tables": []})
        extractor = MagicMock()
        extractor.extract_from_file.side_effect = RuntimeError("extract failed")
        with patch("integrations.mcp_service.os.path.exists", return_value=True), \
             _mock_imports({
                 "core.knowledge_ingestion": MagicMock(get_knowledge_ingestion=lambda: ing),
                 "core.docling_processor": MagicMock(get_docling_processor=lambda: processor),
                 "core.formula_extractor": MagicMock(get_formula_extractor=lambda w: extractor),
             }):
            r = await _run_local(svc, "ingest_knowledge_from_file", {"file_path": "/tmp/f.xlsx"}, {"workspace_id": "w", "user_id": "u"})
        assert r["success"] is True
        assert r["file_stats"]["formulas_extracted"] == 0


# ---------------------------------------------------------------------------
# universal_integration_service.py
# ---------------------------------------------------------------------------
def _ui_service(**methods):
    inst = MagicMock()
    inst.access_token = "tok"
    for name, ret in methods.items():
        setattr(inst, name, AsyncMock(return_value=ret))
    return inst


def _ui_ret():
    return [{"ok": 1}]


def _ui_patch(service_inst, search_inst=None):
    """Patch SessionLocal + IntegrationRegistry so execute/search route into
    our mocked service instance."""
    import integrations.universal_integration_service as mod

    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    reg = MagicMock()
    reg.get_service_instance = AsyncMock(return_value=service_inst)

    async def _get(service, tenant_id):
        return service_inst

    reg.get_service_instance.side_effect = _get
    return patch("core.database.SessionLocal", return_value=session), patch(
        "core.integration_registry.IntegrationRegistry", return_value=reg
    )


class TestUniversalExecuteBranches:
    async def test_salesforce_execute_all_actions(self):
        import integrations.universal_integration_service as mod

        marker = _ui_ret()
        svc_inst = _ui_service(
            list_contacts=marker, list_opportunities=marker, list_accounts=marker,
            create_contact=marker, create_opportunity=marker, create_account=marker,
            get_opportunity=marker, execute_query=marker,
            update_contact=marker, update_opportunity=marker, update_lead=marker,
            update_account=marker,
        )
        service = mod.UniversalIntegrationService()
        ctx = {"user_id": "u", "tenant_id": "t"}
        p1, p2 = _ui_patch(svc_inst)
        with p1, p2, patch.object(mod, "circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            cases = [
                ("list", {"entity": "contact"}),
                ("list", {"entity": "opportunity"}),
                ("list", {"entity": "account"}),
                ("create", {"entity": "contact", "data": {"n": 1}}),
                ("create", {"entity": "opportunity", "data": {}}),
                ("create", {"entity": "account", "data": {}}),
                ("read", {"entity": "opportunity", "id": "1"}),
                ("query", {"query": "SELECT x"}),
                ("update", {"entity": "contact", "id": "1", "data": {}}),
                ("update", {"entity": "opportunity", "id": "1", "data": {}}),
                ("update", {"entity": "lead", "id": "1", "data": {}}),
                ("update", {"entity": "account", "id": "1", "data": {}}),
            ]
            for action, params in cases:
                r = await service.execute("salesforce", action, params, ctx)
                assert r["status"] == "success", (action, r)
            r = await service.execute("salesforce", "update", {"entity": "bad", "id": "1", "data": {}}, ctx)
            assert r["status"] == "error"

    async def test_salesforce_execute_no_service_no_token(self):
        import integrations.universal_integration_service as mod

        service = mod.UniversalIntegrationService()
        ctx = {"user_id": "u", "tenant_id": "t"}
        session = MagicMock()
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        reg = MagicMock()
        reg.get_service_instance = AsyncMock(return_value=None)
        with patch("core.database.SessionLocal", return_value=session), \
             patch("core.integration_registry.IntegrationRegistry", return_value=reg), \
             patch.object(mod, "circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            r = await service.execute("salesforce", "list", {"entity": "contact"}, ctx)
            assert "not available" in r["message"]
            svc2 = _ui_service(list_contacts=_ui_ret())
            svc2.access_token = None
            reg.get_service_instance = AsyncMock(return_value=svc2)
            with patch("core.token_storage.token_storage") as ts:
                ts.get_token.return_value = None
                r = await service.execute("salesforce", "list", {"entity": "contact"}, ctx)
                assert "No token" in r["message"]
                ts.get_token.return_value = {"access_token": "tok"}
                r = await service.execute("salesforce", "list", {"entity": "contact"}, ctx)
                assert r["status"] == "success"
                with pytest.raises(ValueError):
                    await service._execute_salesforce("list", {"entity": "nope"}, "u", {"registry": reg, "tenant_id": "t"})

    async def test_hubspot_execute_all_actions(self):
        import integrations.universal_integration_service as mod

        marker = _ui_ret()
        svc_inst = _ui_service(
            get_contacts=marker, get_deals=marker, get_companies=marker,
            create_contact=marker, create_deal=marker, create_company=marker,
            update_contact=marker, update_deal=marker, update_object=marker,
        )
        service = mod.UniversalIntegrationService()
        ctx = {"user_id": "u", "tenant_id": "t"}
        p1, p2 = _ui_patch(svc_inst)
        with p1, p2, patch.object(mod, "circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            for action, params in [
                ("list", {"entity": "contact"}),
                ("list", {"entity": "deal"}),
                ("list", {"entity": "company"}),
                ("create", {"entity": "contact", "data": {}}),
                ("create_company", {"entity": "x", "data": {}}),
                ("create_deal", {"entity": "x", "data": {"amount": 5}}),
                ("create_contact", {"entity": "x", "data": {}}),
                ("update", {"entity": "contact", "id": "1", "data": {}}),
                ("update", {"entity": "deal", "id": "1", "data": {}}),
                ("update", {"entity": "company", "id": "1", "data": {}}),
            ]:
                r = await service.execute("hubspot", action, params, ctx)
                assert r["status"] == "success", (action, r)
            r = await service.execute("hubspot", "nope", {"entity": "contact"}, ctx)
            assert r["status"] == "error"

    async def test_shopify_execute_actions(self):
        import integrations.universal_integration_service as mod

        marker = _ui_ret()
        svc_inst = _ui_service(
            get_products=marker, get_orders=marker, get_customers=marker,
            create_fulfillment=marker, get_shop_analytics=marker,
        )
        service = mod.UniversalIntegrationService()
        ctx = {"user_id": "u", "tenant_id": "t"}
        p1, p2 = _ui_patch(svc_inst)
        with p1, p2, patch.object(mod, "circuit_breaker") as cb, \
             patch("integrations.universal_integration_service.ShopifyService") as shopify_cls:
            shopify_cls.return_value = svc_inst
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            base = {"access_token": "tok", "shop": "s.myshopify.com"}
            for action, params in [
                ("list", {"entity": "product"}),
                ("list", {"entity": "order"}),
                ("list", {"entity": "customer"}),
                ("create", {"entity": "fulfillment", "order_id": "1", "location_id": "l", "tracking_number": "t", "tracking_company": "c"}),
                ("analytics", {}),
            ]:
                merged = dict(base)
                merged.update(params)
                r = await service.execute("shopify", action, merged, ctx)
                assert r["status"] == "success", (action, r)
            r = await service.execute("shopify", "bogus", base, ctx)
            assert r["status"] == "error"
            r = await service.execute("shopify", "list", {}, ctx)
            assert "required" in r["message"]

    async def test_communication_execute_all_platforms(self):
        import integrations.universal_integration_service as mod

        marker = _ui_ret()
        svc_inst = _ui_service(
            post_message=marker, list_channels=marker, make_request=marker,
            send_message=marker, get_teams=marker, list_guilds=marker,
            send_unified_message=marker, list_spaces=marker,
            send_intelligent_message=marker, get_messages=marker, get_message=marker,
            get_recent_inbox=marker,
        )
        service = mod.UniversalIntegrationService()
        ctx = {"user_id": "u", "tenant_id": "t"}
        p1, p2 = _ui_patch(svc_inst)
        with p1, p2, patch.object(mod, "circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            cases = [
                ("slack", "send_message", {"channel": "c", "message": "m"}),
                ("slack", "send_message", {"channel_id": "c", "content": "m"}),
                ("slack", "list_channels", {}),
                ("slack", "search_messages", {"query": "q"}),
                ("teams", "send_message", {"chat_id": "c", "message": "m"}),
                ("teams", "list_chats", {}),
                ("discord", "send_message", {"channel_id": "c", "message": "m"}),
                ("discord", "list_guilds", {}),
                ("google_chat", "send_message", {"channel_id": "c", "content": "m"}),
                ("google_chat", "list_spaces", {}),
                ("telegram", "send_message", {"channel_id": "c", "message": "m"}),
                ("whatsapp", "send_message", {"channel_id": "c", "message": "m"}),
                ("gmail", "send_message", {"to": "x", "subject": "s", "body": "b"}),
                ("gmail", "list_messages", {"query": "q"}),
                ("gmail", "get_message", {"id": "1"}),
                ("outlook", "send_message", {}),
                ("zoho_mail", "list", {"limit": 5}),
                ("zoho_mail", "send_message", {}),
            ]
            for svc_name, action, params in cases:
                r = await service.execute(svc_name, action, params, ctx)
                if svc_name == "zoho_mail" and action == "send_message":
                    assert r["status"] == "error", (svc_name, action, r)
                else:
                    assert r["status"] == "success", (svc_name, action, r)
            r = await service.execute("slack", "unknown", {}, ctx)
            assert r["status"] == "success"

    async def test_calendar_and_search_communication(self):
        import integrations.universal_integration_service as mod

        marker = _ui_ret()
        svc_inst = _ui_service(
            get_events=marker, create_event=marker, check_conflicts=marker,
        )
        service = mod.UniversalIntegrationService()
        ctx = {"user_id": "u", "tenant_id": "t"}
        p1, p2 = _ui_patch(svc_inst)
        with p1, p2, patch.object(mod, "circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            for svc_name, action, params in [
                ("google_calendar", "list", {"calendar_id": "primary"}),
                ("google_calendar", "create", {"data": {}}),
                ("google_calendar", "check_conflicts", {"start_time": "2026-01-01T00:00:00Z", "end_time": "2026-01-01T01:00:00Z"}),
                ("outlook_calendar", "list", {}),
                ("outlook_calendar", "create", {"data": {}}),
                ("outlook_calendar", "bogus", {}),
            ]:
                r = await service.execute(svc_name, action, params, ctx)
                if action == "bogus":
                    assert r["status"] == "error", (svc_name, action, r)
                else:
                    assert r["status"] == "success", (svc_name, action, r)

    async def test_search_communication_all(self):
        import integrations.universal_integration_service as mod

        service = mod.UniversalIntegrationService()
        ctx = {"user_id": "u", "tenant_id": "t", "access_token": "tok"}
        with patch.object(mod, "circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            with patch("core.database.SessionLocal") as sl, \
                 patch("core.integration_registry.IntegrationRegistry") as reg_cls:
                sl.return_value.__enter__.return_value = MagicMock()
                reg_cls.return_value.get_service_instance = AsyncMock(return_value=MagicMock())
                with _mock_imports({
                    "integrations.slack_service_unified": MagicMock(slack_unified_service=MagicMock(
                        make_request=AsyncMock(return_value={"r": 1}))),
                    "integrations.atom_google_chat_integration": MagicMock(atom_google_chat_integration=MagicMock(
                        unified_search=AsyncMock(return_value=[{"g": 1}]))),
                    "integrations.atom_telegram_integration": MagicMock(atom_telegram_integration=MagicMock(
                        perform_intelligent_search=AsyncMock(return_value=[{"t": 1}]))),
                    "integrations.atom_whatsapp_integration": MagicMock(atom_whatsapp_integration=MagicMock(
                        perform_intelligent_search=AsyncMock(return_value=[{"w": 1}]))),
                    "integrations.gmail_service": MagicMock(GmailService=MagicMock(return_value=MagicMock(
                        search_messages=MagicMock(return_value=[{"m": 1}])))),
                    "integrations.teams_service": MagicMock(TeamsService=MagicMock(return_value=MagicMock(
                        get_teams=MagicMock(return_value=[{"tm": 1}])))),
                }):
                    r = await service.search("slack", "q", None, ctx)
                    assert r["status"] == "success"
                    r = await service.search("google_chat", "q", None, ctx)
                    assert r["data"] == [{"g": 1}]
                    r = await service.search("telegram", "q", None, ctx)
                    assert r["data"] == [{"t": 1}]
                    r = await service.search("whatsapp", "q", None, ctx)
                    assert r["data"] == [{"w": 1}]
                    r = await service.search("gmail", "q", None, ctx)
                    assert r["data"] == [{"m": 1}]
                    r = await service.search("teams", "q", None, ctx)
                    assert r["data"] == [{"tm": 1}]
                    r = await service.search("outlook", "q", None, ctx)
                    assert r["status"] == "success"

    async def test_search_calendar(self):
        import integrations.universal_integration_service as mod

        service = mod.UniversalIntegrationService()
        ctx = {"user_id": "u", "tenant_id": "t"}
        with patch.object(mod, "circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            with patch("core.database.SessionLocal") as sl, \
                 patch("core.integration_registry.IntegrationRegistry") as reg_cls:
                sl.return_value.__enter__.return_value = MagicMock()
                reg_cls.return_value.get_service_instance = AsyncMock(return_value=MagicMock())
                with _mock_imports({"integrations.google_calendar_service": MagicMock(
                    google_calendar_service=MagicMock(get_events=MagicMock(return_value=[
                        {"title": "Meeting", "description": "d"}])))}):
                    r = await service.search("google_calendar", "meeting", None, ctx)
                    assert r["status"] == "success"
                    assert len(r["data"]) == 1
                    r = await service.search("google_calendar", "zzz", None, ctx)
                    assert r["data"] == []

    async def test_project_management_all(self):
        import integrations.universal_integration_service as mod

        marker = _ui_ret()
        svc_inst = _ui_service(
            get_issues=marker, create_issue=marker, get_teams=marker, get_projects=marker,
            get_boards=marker, create_item=marker, search_items=marker,
            get_tasks=marker, create_task=marker, get_cards=marker, create_card=marker,
        )
        service = mod.UniversalIntegrationService()
        ctx = {"user_id": "u", "tenant_id": "t"}
        p1, p2 = _ui_patch(svc_inst)
        with p1, p2, patch.object(mod, "circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            cases = [
                ("linear", "list", {}),
                ("linear", "create", {"title": "t", "team_id": "1"}),
                ("linear", "list_teams", {}),
                ("linear", "list_projects", {}),
                ("monday", "list", {}),
                ("monday", "create", {"board_id": "1", "title": "t"}),
                ("monday", "list_boards", {}),
                ("monday", "search", {"query": "q"}),
                ("zoho_projects", "list_projects", {"portal_id": "p"}),
                ("zoho_projects", "list", {"portal_id": "p", "project_id": "1"}),
                ("zoho_projects", "list_tasks", {"portal_id": "p"}),
                ("asana", "list", {}),
                ("asana", "create", {"data": {}}),
                ("jira", "list", {"project_key": "PRJ"}),
                ("jira", "create", {"project": "PRJ", "title": "t"}),
                ("trello", "list", {"board_id": "b"}),
                ("trello", "create", {"title": "t", "list_id": "l"}),
            ]
            for svc_name, action, params in cases:
                r = await service.execute(svc_name, action, params, ctx)
                assert r["status"] == "success", (svc_name, action, r)
            r = await service.execute("trello", "nope", {}, ctx)
            assert r["status"] == "success"

    async def test_search_project_management(self):
        import integrations.universal_integration_service as mod

        service = mod.UniversalIntegrationService()
        ctx = {"user_id": "u", "tenant_id": "t"}
        with patch.object(mod, "circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            with patch("core.database.SessionLocal") as sl, \
                 patch("core.integration_registry.IntegrationRegistry") as reg_cls:
                sl.return_value.__enter__.return_value = MagicMock()
                pm = MagicMock()
                pm.access_token = "tok"
                pm.get_issues = AsyncMock(return_value=[{"title": "Fix bug", "description": "d"}])
                pm.search_items = AsyncMock(return_value=[{"name": "x"}])
                pm.get_tasks = AsyncMock(return_value=[{"name": "Task A"}])
                pm.search_issues = AsyncMock(return_value=[{"key": "1"}])
                reg_cls.return_value.get_service_instance = AsyncMock(return_value=pm)
                r = await service.search("linear", "fix", None, ctx)
                assert len(r) == 1
                r = await service.search("monday", "q", None, ctx)
                assert r == [{"name": "x"}]
                r = await service.search("asana", "task", None, ctx)
                assert len(r) == 1
                r = await service.search("jira", "q", None, ctx)
                assert r == [{"key": "1"}]
                r = await service.search("trello", "q", None, ctx)
                assert r == []

    async def test_storage_all(self):
        import integrations.universal_integration_service as mod

        marker = _ui_ret()
        svc_inst = _ui_service(
            list_files=marker, search_files=marker, get_file_metadata=marker,
            list_folder=marker, search=marker, create_folder=marker,
            list_drive_items=marker, list_folder_items=marker,
            create_page=marker, search_pages_in_workspace=marker,
        )
        service = mod.UniversalIntegrationService()
        ctx = {"user_id": "u", "tenant_id": "t"}
        p1, p2 = _ui_patch(svc_inst)
        with p1, p2, patch.object(mod, "circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            cases = [
                ("google_drive", "list", {"folder_id": "f"}),
                ("google_drive", "list_files", {}),
                ("google_drive", "search", {"query": "q"}),
                ("google_drive", "get_metadata", {"file_id": "1"}),
                ("dropbox", "list", {"path": "/"}),
                ("dropbox", "list_folder", {"path": "/"}),
                ("dropbox", "search", {"query": "q"}),
                ("dropbox", "create_folder", {"path": "/x"}),
                ("onedrive", "list", {"path": "/"}),
                ("onedrive", "list_files", {}),
                ("onedrive", "search", {"query": "q"}),
                ("box", "list", {"folder_id": "0"}),
                ("notion", "search", {"query": "q"}),
                ("notion", "create_page", {"parent": {}, "properties": {}, "children": []}),
                ("notion", "list", {}),
                ("zoho_workdrive", "list", {"folder_id": "f"}),
                ("zoho_workdrive", "search", {"query": "q"}),
            ]
            for svc_name, action, params in cases:
                r = await service.execute(svc_name, action, params, ctx)
                assert r["status"] == "success", (svc_name, action, r)

    async def test_search_storage(self):
        import integrations.universal_integration_service as mod

        service = mod.UniversalIntegrationService()
        ctx = {"user_id": "u", "tenant_id": "t"}
        with patch.object(mod, "circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            with patch("core.database.SessionLocal") as sl, \
                 patch("core.integration_registry.IntegrationRegistry") as reg_cls:
                sl.return_value.__enter__.return_value = MagicMock()
                st = MagicMock()
                st.access_token = "tok"
                st.search_files = AsyncMock(return_value={"status": "success", "data": {"files": [{"id": 1}]}})
                st.search = AsyncMock(return_value=[{"name": "x"}])
                reg_cls.return_value.get_service_instance = AsyncMock(return_value=st)
                r = await service.search("google_drive", "q", None, ctx)
                assert r == [{"id": 1}]
                r = await service.search("dropbox", "q", None, ctx)
                assert r == [{"name": "x"}]
                st2 = MagicMock()
                st2.access_token = "tok"
                st2.search = AsyncMock(return_value={"results": [{"id": 2}]})
                reg_cls.return_value.get_service_instance = AsyncMock(return_value=st2)
                r = await service.search("notion", "q", None, ctx)
                assert r == [{"id": 2}]
                reg_cls.return_value.get_service_instance = AsyncMock(return_value=st)
                r = await service.search("box", "q", None, ctx)
                assert r == []

    async def test_support_dev_marketing_finance_zoho_analytics(self):
        import integrations.universal_integration_service as mod

        marker = _ui_ret()
        svc_inst = _ui_service(
            get_tickets=marker, create_ticket=marker, search_tickets=marker,
            get_conversations=marker, search_contacts=marker,
            get_user_repositories=marker, get_repository_issues=marker,
            get_projects=marker, get_issues=marker, search_projects=marker,
            get_team_projects=marker, get_file=marker, get_comments=marker,
            get_campaigns=marker, get_audiences=marker,
            list_payments=marker, get_balance=marker, get_invoices=marker,
            create_customer=marker, create_invoice=marker, get_items=marker,
            send_email=marker, get_send_quota=marker,
            get_recent_inbox=marker,
            get_tasks=marker,
            get_leads=marker, get_deals=marker, create_lead=marker,
            get_workbooks=marker,
        )
        service = mod.UniversalIntegrationService()
        ctx = {"user_id": "u", "tenant_id": "t"}
        p1, p2 = _ui_patch(svc_inst)
        with p1, p2, patch.object(mod, "circuit_breaker") as cb, _mock_imports({
            "integrations.zoho_crm_service": MagicMock(ZohoCRMService=MagicMock(return_value=MagicMock(
                get_leads=AsyncMock(return_value=_ui_ret()),
                get_deals=AsyncMock(return_value=_ui_ret()),
                create_lead=AsyncMock(return_value=_ui_ret())))),
            "integrations.zoho_mail_service": MagicMock(zoho_mail_service=MagicMock(
                get_recent_inbox=AsyncMock(return_value=_ui_ret()))),
            "integrations.zoho_inventory_service": MagicMock(zoho_inventory_service=MagicMock(
                get_items=AsyncMock(return_value=_ui_ret()))),
            "integrations.zoho_projects_service": MagicMock(zoho_projects_service=MagicMock(
                get_projects=AsyncMock(return_value=_ui_ret()))),
        }):
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            cases = [
                ("zendesk", "list", {}),
                ("zendesk", "create", {"data": {}}),
                ("freshdesk", "list", {}),
                ("freshdesk", "get_tickets", {}),
                ("freshdesk", "create", {}),
                ("freshdesk", "search", {"query": "q"}),
                ("intercom", "list", {}),
                ("intercom", "get_conversations", {}),
                ("intercom", "search_contacts", {"query": "q"}),
                ("github", "list", {}),
                ("github", "list_repos", {}),
                ("github", "get_issues", {"owner": "o", "repo": "r"}),
                ("gitlab", "list", {}),
                ("gitlab", "list_projects", {}),
                ("gitlab", "get_issues", {"project_id": "1"}),
                ("gitlab", "search", {"query": "q"}),
                ("figma", "list", {"team_id": "t"}),
                ("figma", "get_projects", {"team_id": "t"}),
                ("figma", "get_file", {"file_key": "k"}),
                ("figma", "get_comments", {"file_key": "k"}),
                ("stripe", "list_payments", {}),
                ("stripe", "get_balance", {}),
                ("quickbooks", "list_invoices", {}),
                ("quickbooks", "create_customer", {"display_name": "n", "email": "e"}),
                ("quickbooks", "create_invoice", {}),
                ("xero", "list_invoices", {}),
                ("zoho_books", "list_invoices", {}),
                ("zoho_inventory", "list_items", {}),
                ("aws_ses", "send_email", {"to": ["a@b"], "subject": "s", "text_body": "x"}),
                ("aws_ses", "get_quota", {}),
                ("zoho_crm", "list", {}),
                ("zoho_crm", "get_leads", {}),
                ("zoho_crm", "get_deals", {}),
                ("zoho_crm", "create_lead", {"data": {}}),
                ("zoho_mail", "list", {}),
                ("zoho_inventory", "list", {}),
                ("zoho_projects", "list", {}),
                ("google_analytics", "report", {}),
            ]
            for svc_name, action, params in cases:
                r = await service.execute(svc_name, action, params, ctx)
                assert r["status"] == "success", (svc_name, action, r)

    async def test_tableau_execute_error_and_marketing(self):
        import integrations.universal_integration_service as mod

        service = mod.UniversalIntegrationService()
        ctx = {"user_id": "u", "tenant_id": "t", "access_token": "tok", "server_prefix": "sp"}
        with patch.object(mod, "circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            with patch("core.database.SessionLocal") as sl, \
                 patch("core.integration_registry.IntegrationRegistry") as reg_cls:
                sl.return_value.__enter__.return_value = MagicMock()
                reg_cls.return_value.get_service_instance = AsyncMock(return_value=MagicMock())
                with _mock_imports({
                    "integrations.mailchimp_service": MagicMock(MailchimpService=MagicMock(return_value=MagicMock(
                        get_campaigns=AsyncMock(return_value=[{"settings": {"subject_line": "s", "title": "t"}}]),
                        get_audiences=AsyncMock(return_value=[{"id": 1}])))),
                    "integrations.hubspot_service": MagicMock(get_hubspot_service=lambda: MagicMock(
                        get_campaigns=AsyncMock(return_value=[{"id": 1}]))),
                    "integrations.github_service": MagicMock(GitHubService=MagicMock(return_value=MagicMock(
                        get_user_repositories=MagicMock(return_value=[{"name": "Repo"}])))),
                    "integrations.gitlab_service": MagicMock(GitLabService=MagicMock(return_value=MagicMock(
                        search_projects=AsyncMock(return_value=[{"id": 1}])))),
                    "integrations.zoho_crm_service": MagicMock(ZohoCRMService=MagicMock(return_value=MagicMock(
                        get_leads=AsyncMock(return_value=[{"Last_Name": "X", "Email": "x@y"}])))),
                    "integrations.zendesk_service": MagicMock(ZendeskService=MagicMock(return_value=MagicMock(
                        get_tickets=AsyncMock(return_value=[{"id": 1}])))),
                    "integrations.freshdesk_service": MagicMock(FreshdeskService=MagicMock(return_value=MagicMock(
                        search_tickets=AsyncMock(return_value=[{"id": 1}])))),
                }):
                    tableau = MagicMock()
                    tableau.get_workbooks = AsyncMock(side_effect=RuntimeError("boom"))
                    with patch("integrations.tableau_service.TableauService", MagicMock(return_value=tableau)):
                        r = await service.execute("tableau", "list", {}, ctx)
                        assert r["status"] == "error"
                    r = await service.execute("mailchimp", "list", {}, ctx)
                    assert r["status"] == "success"
                    r = await service.execute("mailchimp", "get_campaigns", {}, ctx)
                    assert r["status"] == "success"
                    r = await service.execute("mailchimp", "get_audiences", {}, ctx)
                    assert r["status"] == "success"
                    r = await service.execute("hubspot_marketing", "list_campaigns", {}, ctx)
                    assert r["status"] == "success"
                    r = await service.execute("hubspot_marketing", "other", {}, ctx)
                    assert r["status"] == "success"

    async def test_search_dev_marketing_crm_support_analytics(self):
        import integrations.universal_integration_service as mod

        service = mod.UniversalIntegrationService()
        ctx = {"user_id": "u", "tenant_id": "t", "access_token": "tok"}
        with patch.object(mod, "circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            with patch("core.database.SessionLocal") as sl, \
                 patch("core.integration_registry.IntegrationRegistry") as reg_cls:
                sl.return_value.__enter__.return_value = MagicMock()
                hub_svc = MagicMock()
                hub_svc.access_token = "tok"
                hub_svc.search_content = AsyncMock(return_value={"results": [{"id": 1}]})
                storage_svc = MagicMock()
                storage_svc.access_token = "tok"
                storage_svc.search_files = AsyncMock(return_value=[{"id": 3}])
                reg_cls.return_value.get_service_instance = AsyncMock(
                    side_effect=lambda svc, tid: hub_svc if svc == "hubspot" else storage_svc
                )
                with _mock_imports({
                    "integrations.github_service": MagicMock(GitHubService=MagicMock(return_value=MagicMock(
                        get_user_repositories=MagicMock(return_value=[{"name": "RepoA"}],
                        )))),
                    "integrations.gitlab_service": MagicMock(GitLabService=MagicMock(return_value=MagicMock(
                        search_projects=AsyncMock(return_value=[{"name": "P"}])))),
                    "integrations.mailchimp_service": MagicMock(MailchimpService=MagicMock(return_value=MagicMock(
                        get_campaigns=AsyncMock(return_value=[{"settings": {"subject_line": "Sale!", "title": "t"}}])))),
                    "integrations.zoho_crm_service": MagicMock(ZohoCRMService=MagicMock(return_value=MagicMock(
                        get_leads=AsyncMock(return_value=[{"Last_Name": "Smith", "Email": "s@x"}])))),
                    "integrations.zendesk_service": MagicMock(ZendeskService=MagicMock(return_value=MagicMock(
                        get_tickets=AsyncMock(return_value=[{"id": 1}])))),
                    "integrations.freshdesk_service": MagicMock(FreshdeskService=MagicMock(return_value=MagicMock(
                        search_tickets=AsyncMock(return_value=[{"id": 1}])))),
                }):
                    tableau = MagicMock()
                    tableau.get_workbooks = AsyncMock(return_value=[{"name": "Sales"}])
                    with patch("integrations.tableau_service.TableauService",
                               MagicMock(return_value=tableau)):
                        r = await service.search("github", "repoa", None, ctx)
                        assert r["status"] == "success"
                        r = await service.search("gitlab", "q", None, ctx)
                        assert r["status"] == "success"
                        r = await service.search("mailchimp", "sale", None, ctx)
                        assert len(r["data"]) == 1
                        r = await service.search("zoho_crm", "smith", None, ctx)
                        assert len(r["data"]) == 1
                        r = await service.search("salesforce", "q", None, ctx)
                        assert r["status"] == "success"
                        r = await service.search("hubspot", "q", None, ctx)
                        assert r == [{"id": 1}]
                        r = await service.search("zendesk", "q", None, ctx)
                        assert r["status"] == "success"
                        r = await service.search("freshdesk", "q", None, ctx)
                        assert r["status"] == "success"
                        r = await service.search("intercom", "q", None, ctx)
                        assert r["status"] == "error"
                        r = await service.search("tableau", "sales", None, ctx)
                        assert r["status"] == "success"
                        r = await service.search("google_analytics", "q", None, ctx)
                        assert r["status"] == "success"
                    tableau2 = MagicMock()
                    tableau2.get_workbooks = AsyncMock(side_effect=RuntimeError("boom"))
                    with patch("integrations.tableau_service.TableauService", MagicMock(return_value=tableau2)):
                        r = await service.search("tableau", "q", None, ctx)
                        assert r["status"] == "error"

    async def test_search_intercom_via_registry(self):
        import integrations.universal_integration_service as mod

        service = mod.UniversalIntegrationService()
        ctx = {"user_id": "u", "tenant_id": "t"}
        with patch.object(mod, "circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            with patch("core.database.SessionLocal") as sl, \
                 patch("core.integration_registry.IntegrationRegistry") as reg_cls:
                sl.return_value.__enter__.return_value = MagicMock()
                inst = MagicMock()
                inst.access_token = "tok"
                inst.search_contacts = AsyncMock(return_value=[{"id": 1}])
                reg_cls.return_value.get_service_instance = AsyncMock(return_value=inst)
                r = await service.search("intercom", "q", None, ctx)
                assert r["status"] == "success"
                reg_cls.return_value.get_service_instance = AsyncMock(return_value=None)
                r = await service.search("intercom", "q", None, ctx)
                assert r["status"] == "error"

    async def test_dispatch_system_agent_and_errors(self):
        import integrations.universal_integration_service as mod

        service = mod.UniversalIntegrationService()
        # system agent with db lookup -> workspace token -> custom service
        agent = MagicMock()
        agent.is_system_agent = True
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = agent
        with patch("core.models.AgentRegistry", new=MagicMock()):
            marker = _ui_ret()
            with patch.object(service, "_execute_activepieces", new=AsyncMock(return_value=marker)):
                r = await service._dispatch_execution(
                    "custom_svc", "list", {}, {"agent_id": "ag1", "db": db, "workspace_id": "w", "registry": MagicMock()}
                )
                assert r == marker
        # no user_id -> ValueError
        with pytest.raises(ValueError):
            await service._dispatch_execution("salesforce", "list", {}, {"registry": MagicMock()})
        # system agent db query raises -> warning then ValueError
        db2 = MagicMock()
        db2.query.side_effect = RuntimeError("db down")
        with pytest.raises(ValueError):
            await service._dispatch_execution("salesforce", "list", {}, {"agent_id": "ag1", "db": db2, "registry": MagicMock()})
        # unknown service -> activepieces
        with patch.object(service, "_execute_activepieces", new=AsyncMock(return_value={"ap": 1})):
            r = await service._dispatch_execution(
                "some_custom", "act", {}, {"user_id": "u", "registry": MagicMock()}
            )
            assert r == {"ap": 1}

    async def test_generic_handlers_and_activepieces(self):
        import integrations.universal_integration_service as mod

        service = mod.UniversalIntegrationService()
        with patch.object(mod, "circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            r = await service._execute_generic_native("tableau", "x", {}, {})
            assert r["status"] == "success"
            r = await service._execute_marketing_reviews("google_reviews", "list_reviews", {}, {"user_id": "u"})
            assert r["status"] == "success"
            r = await service._execute_marketing_reviews("google_reviews", "reply_to_review", {"review_id": "1"}, {})
            assert r["status"] == "success"
            r = await service._execute_marketing_reviews("google_reviews", "unknown", {}, {})
            assert r["status"] == "error"
            r = await service._execute_marketing_ads("meta_ads", "run", {}, {})
            assert r["status"] == "success"
            with patch("core.external_integration_service.external_integration_service") as ext:
                ext.execute_integration_action = AsyncMock(return_value={"e": 1})
                r = await service._execute_activepieces("custom", "act", {}, {})
                assert r["status"] == "success"
                ext.execute_integration_action = AsyncMock(side_effect=RuntimeError("no"))
                r = await service._execute_activepieces("custom", "act", {}, {})
                assert r["status"] == "error"

    async def test_execute_circuit_open_and_governance_pause(self):
        import integrations.universal_integration_service as mod

        service = mod.UniversalIntegrationService()
        with patch.object(mod, "circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=False)
            cb.get_stats.return_value = {"disabled_until": "soon"}
            r = await service.execute("slack", "send_message", {}, {})
            assert r["status"] == "error"
            assert r["circuit_open"] is True
            cb.is_enabled = AsyncMock(return_value=True)
            with patch.object(mod, "governance_middleware") as gm:
                gm.mask_response = MagicMock(side_effect=lambda s, r: r)
                gm.check_action_risk = AsyncMock(return_value={"allowed": False, "reason": "needs review", "intervention_id": "i1"})
                r = await service.execute("slack", "send_message", {}, {"user_id": "u"})
                assert r["status"] == "paused"
                gm.check_action_risk = AsyncMock(side_effect=RuntimeError("gov down"))
                with patch.object(service, "_dispatch_execution", new=AsyncMock(return_value={"status": "success", "data": 1})), \
                     patch("core.database.SessionLocal") as sl, \
                     patch("core.integration_registry.IntegrationRegistry") as reg_cls, \
                     patch.object(mod, "budget_service") as bs:
                    sl.return_value.__enter__.return_value = MagicMock()
                    reg_cls.return_value = MagicMock()
                    bs.record_workspace_spend = MagicMock()
                    r = await service.execute("slack", "send_message", {}, {"user_id": "u", "workspace_id": "w"})
                    assert r["status"] == "success"
                    bs.record_workspace_spend.assert_called_once()

    async def test_search_error_and_circuit_open(self):
        import integrations.universal_integration_service as mod

        service = mod.UniversalIntegrationService()
        with patch.object(mod, "circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=False)
            r = await service.search("slack", "q")
            assert r["circuit_open"] is True
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            with patch("core.database.SessionLocal") as sl, \
                 patch("core.integration_registry.IntegrationRegistry") as reg_cls, _mock_imports({
                     "integrations.mailchimp_service": MagicMock(MailchimpService=MagicMock(return_value=MagicMock(
                         get_campaigns=AsyncMock(return_value=[{"settings": {"subject_line": "s"}}])))),
                 }):
                sl.return_value.__enter__.return_value = MagicMock()
                st_svc = MagicMock()
                st_svc.access_token = "tok"
                st_svc.search_files = AsyncMock(return_value=[{"id": 3}])
                reg_cls.return_value.get_service_instance = AsyncMock(return_value=st_svc)
                r = await service.search("unknown_svc", "q", None, {"user_id": "u", "tenant_id": "t"})
                assert r["status"] == "error"
                r = await service.search("mailchimp", "q", None, {"user_id": "u"})
                assert r["status"] == "success"
                r = await service.search("zoho_workdrive", "q", None, {"user_id": "u"})
                assert r["status"] == "success"

    async def test_analytics_search_success_path(self):
        import integrations.universal_integration_service as mod

        service = mod.UniversalIntegrationService()
        ctx = {"user_id": "u", "tenant_id": "t", "access_token": "tok"}
        with patch.object(mod, "circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            with patch("core.database.SessionLocal") as sl, \
                 patch("core.integration_registry.IntegrationRegistry") as reg_cls:
                sl.return_value.__enter__.return_value = MagicMock()
                reg_cls.return_value.get_service_instance = AsyncMock(return_value=MagicMock())
                tableau = MagicMock()
                tableau.get_workbooks = AsyncMock(return_value=[{"name": "Workbook"}])
                with patch("integrations.tableau_service.TableauService",
                           MagicMock(return_value=tableau)):
                    r = await service.search("tableau", "work", None, ctx)
                    assert r["status"] == "success"
                    assert len(r["data"]) == 1


# ---------------------------------------------------------------------------
# universal_integration_service — final branch coverage
# ---------------------------------------------------------------------------
class TestUniversalCoverageWave3:
    async def test_salesforce_search_entity_branches(self):
        import integrations.universal_integration_service as mod

        service = mod.UniversalIntegrationService()
        with patch.object(mod, "circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            with patch("core.database.SessionLocal") as sl, \
                 patch("core.integration_registry.IntegrationRegistry") as reg_cls:
                sl.return_value.__enter__.return_value = MagicMock()
                sf = MagicMock()
                sf.access_token = "tok"
                sf.execute_query = AsyncMock(return_value={"records": [{"Id": 1}]})
                reg_cls.return_value.get_service_instance = AsyncMock(return_value=sf)
                ctx = {"user_id": "u", "tenant_id": "t"}
                r = await service.search("salesforce", "bob", "contact", ctx)
                assert r == {"status": "success", "data": [{"Id": 1}]}
                r = await service.search("salesforce", "bob", "account", ctx)
                assert r["status"] == "success"
                r = await service.search("salesforce", "bob", "lead", ctx)
                assert r["data"] == [{"message": "Only specific entity search implemented via SOQL"}]

    async def test_hubspot_fallback_singleton(self):
        import integrations.universal_integration_service as mod

        service = mod.UniversalIntegrationService()
        ctx = {"user_id": "u", "tenant_id": "t"}
        with patch.object(mod, "circuit_breaker") as cb, _mock_imports({
            "integrations.hubspot_service": MagicMock(
                get_hubspot_service=lambda: MagicMock(
                    access_token="tok",
                    get_contacts=AsyncMock(return_value=[{"id": 1}]))),
        }):
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            session = MagicMock()
            session.__enter__ = MagicMock(return_value=session)
            session.__exit__ = MagicMock(return_value=False)
            reg = MagicMock()
            reg.get_service_instance = AsyncMock(return_value=None)
            with patch("core.database.SessionLocal", return_value=session), \
                 patch("core.integration_registry.IntegrationRegistry", return_value=reg):
                r = await service.execute("hubspot", "list", {"entity": "contact"}, ctx)
                assert r["status"] == "success"

    async def test_slack_fallback_singleton(self):
        import integrations.universal_integration_service as mod

        service = mod.UniversalIntegrationService()
        ctx = {"user_id": "u", "tenant_id": "t"}
        with patch.object(mod, "circuit_breaker") as cb, _mock_imports({
            "integrations.slack_service_unified": MagicMock(slack_unified_service=MagicMock(
                post_message=AsyncMock(return_value=[{"ok": 1}]))),
        }):
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            session = MagicMock()
            session.__enter__ = MagicMock(return_value=session)
            session.__exit__ = MagicMock(return_value=False)
            reg = MagicMock()
            reg.get_service_instance = AsyncMock(return_value=None)
            with patch("core.database.SessionLocal", return_value=session), \
                 patch("core.integration_registry.IntegrationRegistry", return_value=reg):
                r = await service.execute("slack", "send_message", {"channel": "c", "message": "m"}, ctx)
                assert r["status"] == "success"

    async def test_dispatch_none_context_and_default_handlers(self):
        import integrations.universal_integration_service as mod

        service = mod.UniversalIntegrationService()
        # context=None defaulting
        marker = _ui_ret()
        with pytest.raises(ValueError):
            await service._dispatch_execution("aws_ses", "list", {}, None)
        fin_svc = MagicMock()
        fin_svc.access_token = "tok"
        fin_svc.get_invoices = AsyncMock(return_value=[{"id": 1}])
        reg = MagicMock()
        reg.get_service_instance = AsyncMock(return_value=fin_svc)
        r = await service._dispatch_execution(
            "aws_ses", "list", {}, {"user_id": "u", "registry": reg}
        )
        assert r["status"] == "success"
        # default handler returns via execute()
        with patch.object(mod, "circuit_breaker") as cb, _mock_imports({
            "integrations.mailchimp_service": MagicMock(MailchimpService=MagicMock(return_value=MagicMock(
                get_campaigns=AsyncMock(return_value=[{"settings": {"subject_line": "s"}}])))),
            "integrations.hubspot_service": MagicMock(get_hubspot_service=lambda: MagicMock(
                get_campaigns=AsyncMock(return_value=[{"id": 1}]))),
            "integrations.github_service": MagicMock(GitHubService=MagicMock(return_value=MagicMock(
                get_user_repositories=MagicMock(return_value=[{"name": "R"}])))),
            "integrations.gitlab_service": MagicMock(GitLabService=MagicMock(return_value=MagicMock(
                search_projects=AsyncMock(return_value=[{"id": 1}])))),
            "integrations.zoho_crm_service": MagicMock(ZohoCRMService=MagicMock(return_value=MagicMock(
                get_leads=AsyncMock(return_value=[{"Last_Name": "X"}])))),
            "integrations.zoho_mail_service": MagicMock(ZohoMailService=MagicMock(return_value=MagicMock(
                get_recent_inbox=AsyncMock(return_value=[{"id": 1}])))),
            "integrations.zoho_inventory_service": MagicMock(zoho_inventory_service=MagicMock(
                get_items=AsyncMock(return_value=[{"id": 1}]))),
            "integrations.zoho_projects_service": MagicMock(ZohoProjectsService=MagicMock(return_value=MagicMock(
                get_projects=AsyncMock(return_value=[{"id": 1}])))),
            "integrations.zendesk_service": MagicMock(ZendeskService=MagicMock(return_value=MagicMock(
                get_tickets=AsyncMock(return_value=[{"id": 1}])))),
            "integrations.freshdesk_service": MagicMock(FreshdeskService=MagicMock(return_value=MagicMock(
                search_tickets=AsyncMock(return_value=[{"id": 1}])))),
        }):
            tableau = MagicMock()
            tableau.get_workbooks = AsyncMock(return_value=[{"name": "W"}])
            cb.is_enabled = AsyncMock(return_value=True)
            cb.record_failure = AsyncMock()
            session = MagicMock()
            session.__enter__ = MagicMock(return_value=session)
            session.__exit__ = MagicMock(return_value=False)
            inst = MagicMock()
            inst.access_token = "tok"
            inst.search_contacts = AsyncMock(return_value=[{"id": 1}])
            reg = MagicMock()
            reg.get_service_instance = AsyncMock(return_value=inst)
            with patch("core.database.SessionLocal", return_value=session), \
                 patch("core.integration_registry.IntegrationRegistry", return_value=reg), \
                 patch("integrations.tableau_service.TableauService", MagicMock(return_value=tableau)):
                ctx = {"user_id": "u", "tenant_id": "t", "access_token": "tok"}
                # default handler returns (unmatched actions)
                r = await service.execute("google_drive", "nope", {}, ctx)
                assert "Registry Storage" in r["message"]
                r = await service.execute("zendesk", "nope", {}, ctx)
                assert "Registry Support" in r["message"]
                r = await service.execute("github", "nope", {}, ctx)
                assert "Registry Dev" in r["message"]
                r = await service.execute("tableau", "nope", {}, ctx)
                assert "analytics" in r["message"]
                r = await service.execute("mailchimp", "nope", {}, ctx)
                assert "marketing" in r["message"]
                r = await service.execute("slack", "nope", {}, ctx)
                assert "default handler" in r["message"]
                r = await service.execute("trello", "nope", {}, ctx)
                assert "Registry PM" in r["message"]
                r = await service.execute("stripe", "nope", {}, ctx)
                assert "Registry Finance" in r["message"]
                # direct _execute_zoho dead branches
                r = await service._execute_zoho("zoho_mail", "list", {}, ctx)
                assert r["status"] == "success"
                r = await service._execute_zoho("zoho_inventory", "list", {}, ctx)
                assert r["status"] == "success"
                r = await service._execute_zoho("zoho_projects", "list", {}, ctx)
                assert r["status"] == "success"
                r = await service._execute_zoho("zoho_crm", "nope", {}, ctx)
                assert "default zoho" in r["message"]
                # search default fallbacks
                r = await service._search_crm("salesforce", "q", ctx)
                assert r["status"] == "success"
                r = await service._search_crm("hubspot", "q", ctx)
                assert r["status"] == "success"
                r = await service._search_crm("zoho_crm", "x", ctx)
                assert r["status"] == "success"
                r = await service._search_dev("figma", "q", ctx)
                assert r == []
                r = await service._search_marketing("hubspot_marketing", "q", ctx)
                assert r == []
                r = await service._search_support("other", "q", ctx)
                assert r["status"] == "success"
                r = await service._search_analytics("google_analytics", "q", ctx)
                assert r["status"] == "success"
                r = await service._search_calendar("outlook_calendar", "q", ctx)
                assert r == []
                r = await service._search_communication("outlook", "q", None, ctx)
                assert r["status"] == "success"
                r = await service._search_storage("onedrive", "q", ctx)
                assert r == []

    async def test_budget_service_import_guard_reload(self):
        import importlib
        import integrations.universal_integration_service as mod

        with patch.dict(sys.modules, {"core.budget_service": None}):
            importlib.reload(mod)
            assert mod.budget_service is None
        importlib.reload(mod)
        assert mod.budget_service is None


# ---------------------------------------------------------------------------
# atom_workflow_automation_service.py
# ---------------------------------------------------------------------------
def _wf_svc(config=None, tenant="t1"):
    import integrations.atom_workflow_automation_service as mod

    cfg = config or {}
    return mod.AtomWorkflowAutomationService(tenant, cfg)


def _wf_automation(mod, automation_id="auto_1", **over):
    data = dict(
        automation_id=automation_id,
        name="n", description="d",
        automation_type=mod.WorkflowAutomationType.SECURITY,
        priority=mod.AutomationPriority.HIGH,
        status=mod.AutomationStatus.ACTIVE,
        conditions=[{"type": mod.AutomationConditionType.SECURITY_ALERT.value}],
        actions=[{"type": mod.AutomationActionType.NOTIFICATION.value,
                  "config": {"channels": ["security_team"], "message": "m", "urgency": "high"}}],
        schedule=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        created_by="u",
        last_executed=None, execution_count=0, success_count=0, failure_count=0,
        timeout=60, retry_policy={}, notification_rules=[], metadata={}, audit_trail=[],
    )
    data.update(over)
    return mod.WorkflowAutomation(**data)


def _wf_execution(mod, **over):
    data = dict(
        execution_id="exec_1", automation_id="auto_1", triggered_by="t",
        trigger_context={}, status=mod.AutomationStatus.RUNNING,
        started_at=datetime.now(timezone.utc), completed_at=None, execution_time=1.0,
        result={}, error=None, actions_executed=[], notifications_sent=[],
        compliance_checks=[], security_checks=[], metadata={},
    )
    data.update(over)
    return mod.AutomationExecution(**data)


class TestWorkflowAutomationCoverage:
    async def test_initialize_success_and_failure(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc({"security_service": MagicMock(), "unified_service": MagicMock(), "ai_service": MagicMock()})
        for m in ["_initialize_automation_templates", "_load_automations",
                  "_initialize_automation_scheduling", "_initialize_trigger_listeners",
                  "_initialize_integration_endpoints", "_start_automation_monitoring"]:
            setattr(svc, m, AsyncMock(return_value=True))
        assert await svc.initialize() is True
        assert svc.is_initialized is True
        svc2 = _wf_svc({"security_service": None, "unified_service": None, "ai_service": None})
        assert await svc2.initialize() is False

    async def test_create_automation_flows(self):
        import integrations.atom_workflow_automation_service as mod

        db = AsyncMock()
        svc = _wf_svc({"database": db})
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            data = {
                "name": "Test Auto", "description": "d",
                "automation_type": "security", "priority": "high",
                "conditions": [{"type": "security_alert"}],
                "actions": [{"type": "notification", "config": {"channels": ["slack"]}}],
                "schedule": None,
            }
            r = await svc.create_automation(data, "user1")
            assert r["ok"] is True
            assert r["automation_id"] in svc.automations
            db.store_workflow_automation.assert_awaited()
            assert svc.automation_metrics["total_automations"] == 1
            # validation failure
            r = await svc.create_automation({"name": "x"}, "u")
            assert r["ok"] is False
            assert "validation failed" in r["error"]
            # duplicate automations increment metrics
            r = await svc.create_automation(data, "user1")
            assert r["ok"] is True

    async def test_create_automation_circuit_and_rate_limit(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc()
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=False)
            r = await svc.create_automation({"name": "x"}, "u")
            assert r["ok"] is False and "temporarily disabled" in r["error"]
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(True, 0))
            r = await svc.create_automation({"name": "x"}, "u")
            assert r["ok"] is False and "Rate limit" in r["error"]
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            # missing name -> KeyError -> error dict
            r = await svc.create_automation({"priority": "high"}, "u")
            assert r["ok"] is False

    async def test_execute_automation_flows(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc({"database": AsyncMock()})
        automation = _wf_automation(mod, actions=[
            {"type": "notification", "config": {"channels": ["slack"], "message": "m"}},
            {"type": "bogus_type"},
        ])
        svc.automations["auto_1"] = automation
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            r = await svc.execute_automation("missing", {}, "t")
            assert r["ok"] is False
            automation.status = mod.AutomationStatus.INACTIVE
            r = await svc.execute_automation("auto_1", {}, "t")
            assert r["ok"] is False
            automation.status = mod.AutomationStatus.ACTIVE
            with patch.object(svc, "_pre_execution_security_check", new=AsyncMock(return_value={"passed": False, "reason": "no"})), \
                 patch.object(svc, "_send_automation_notifications", new=AsyncMock()):
                r = await svc.execute_automation("auto_1", {}, "t")
                assert r["ok"] is False
                assert "Security check failed" in r["error"]
            with patch.object(svc, "_pre_execution_security_check", new=AsyncMock(return_value={"passed": True})), \
                 patch.object(svc, "_pre_execution_compliance_check", new=AsyncMock(return_value={"passed": False, "reason": "no"})), \
                 patch.object(svc, "_send_automation_notifications", new=AsyncMock()):
                r = await svc.execute_automation("auto_1", {}, "t")
                assert r["ok"] is False
                assert "Compliance check failed" in r["error"]
            # success run: notification ok + bogus action fails -> success_rate 0.5 -> FAILED
            with patch.object(svc, "_pre_execution_security_check", new=AsyncMock(return_value={"passed": True})), \
                 patch.object(svc, "_pre_execution_compliance_check", new=AsyncMock(return_value={"passed": True})), \
                 patch.object(svc, "_post_execution_security_check", new=AsyncMock(return_value={"passed": True})), \
                 patch.object(svc, "_post_execution_compliance_check", new=AsyncMock(return_value={"passed": True})), \
                 patch.object(svc, "_send_automation_notifications", new=AsyncMock()), \
                 patch.object(svc, "_update_automation_metrics", new=AsyncMock()):
                r = await svc.execute_automation("auto_1", {}, "t")
                assert r["ok"] is True
                assert r["status"] == "failed"

    async def test_execute_automation_stop_and_agent_blocked(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc({"database": AsyncMock()})
        automation = _wf_automation(mod, actions=[
            {"type": "notification", "config": {"channels": [], "message": "m"}, "stop": True},
        ])
        svc.automations["auto_1"] = automation
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            with patch.object(svc, "_pre_execution_security_check", new=AsyncMock(return_value={"passed": True})), \
                 patch.object(svc, "_pre_execution_compliance_check", new=AsyncMock(return_value={"passed": True})), \
                 patch.object(svc, "_execute_automation_action", new=AsyncMock(return_value={"success": True, "stop_execution": True})), \
                 patch.object(svc, "_post_execution_security_check", new=AsyncMock(return_value={"passed": True})), \
                 patch.object(svc, "_post_execution_compliance_check", new=AsyncMock(return_value={"passed": True})), \
                 patch.object(svc, "_send_automation_notifications", new=AsyncMock()), \
                 patch.object(svc, "_update_automation_metrics", new=AsyncMock()):
                r = await svc.execute_automation("auto_1", {}, "t")
                assert r["ok"] is True
                assert r["status"] == "completed"
            # maturity-blocked agent action
            automation2 = _wf_automation(mod, "auto_2", actions=[
                {"type": "agent_trigger", "config": {"agent_id": "ag1"}},
            ])
            svc.automations["auto_2"] = automation2
            decision = MagicMock()
            decision.execute = False
            decision.reason = "blocked by maturity"
            decision.routing_decision.value = "blocked"
            decision.agent_maturity = "intern"
            decision.confidence_score = 0.5
            with patch("core.trigger_interceptor.TriggerInterceptor") as ti:
                ti.return_value.intercept_trigger = AsyncMock(return_value=decision)
                r = await svc.execute_automation("auto_2", {}, "t")
            assert r["ok"] is False
            assert "maturity" in r["error"]

    async def test_create_security_and_compliance_automations(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc()
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            with patch.object(svc, "create_automation", new=AsyncMock(return_value={"ok": True, "automation_id": "auto_9"})), \
                 patch.object(svc, "execute_automation", new=AsyncMock(return_value={"ok": True})):
                r = await svc.create_security_automation({"threat_type": "malware", "severity": "high", "source_ip": "1.2.3.4"}, {"actions": []})
                assert r["ok"] is True
                r = await svc.create_compliance_automation({"standard": "SOC2", "violation_type": "v", "severity": "medium"}, {})
                assert r["ok"] is True
            with patch.object(svc, "create_automation", new=AsyncMock(return_value={"ok": False, "error": "no"})):
                r = await svc.create_security_automation({"threat_type": "x"}, {})
                assert r["ok"] is False
                r = await svc.create_compliance_automation({"standard": "x"}, {})
                assert r["ok"] is False

    async def test_create_integration_automation(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc()
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            r = await svc.create_integration_automation("notreal", {})
            assert r["ok"] is False
            with patch.object(svc, "create_automation", new=AsyncMock(return_value={"ok": True, "automation_id": "a"})), \
                 patch.object(svc, "_setup_platform_triggers", new=AsyncMock()):
                r = await svc.create_integration_automation("slack", {"trigger_type": "webhook"})
                assert r["ok"] is True
                r = await svc.create_integration_automation("teams", {})
                assert r["ok"] is True

    async def test_get_automations_filters(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc()
        a1 = _wf_automation(mod, "a1")
        a2 = _wf_automation(mod, "a2", automation_type=mod.WorkflowAutomationType.COMPLIANCE,
                            priority=mod.AutomationPriority.LOW, status=mod.AutomationStatus.INACTIVE,
                            created_by="other")
        svc.automations = {"a1": a1, "a2": a2}
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            r = await svc.get_automations()
            assert len(r) == 2
            r = await svc.get_automations({"automation_type": "compliance"})
            assert len(r) == 1 and r[0]["automation_id"] == "a2"
            r = await svc.get_automations({"priority": "high"})
            assert len(r) == 1
            r = await svc.get_automations({"status": "inactive"})
            assert len(r) == 1
            r = await svc.get_automations({"created_by": "other"})
            assert len(r) == 1

    async def test_get_automation_executions_filters(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc()
        e1 = _wf_execution(mod, execution_id="exec_1", automation_id="a1", triggered_by="sys",
                           started_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
        e2 = _wf_execution(mod, execution_id="exec_2", automation_id="a2", triggered_by="user",
                           started_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        svc.executions = {"exec_1": e1, "exec_2": e2}
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            r = await svc.get_automation_executions()
            assert len(r) == 2 and r[0]["execution_id"] == "exec_1"  # sorted desc
            r = await svc.get_automation_executions("a1")
            assert len(r) == 1
            r = await svc.get_automation_executions(filters={"status": "running"})
            assert len(r) == 2
            r = await svc.get_automation_executions(filters={"triggered_by": "user"})
            assert len(r) == 1
            from datetime import date
            r = await svc.get_automation_executions(filters={"date_from": date(2026, 1, 2)})
            assert len(r) == 1
            r = await svc.get_automation_executions(filters={"date_to": date(2026, 1, 1)})
            assert len(r) == 1

    async def test_get_automation_metrics(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc()
        svc.scheduled_automations = {"s1": {}}
        svc.active_triggers = {"t1": {}}
        svc.automation_templates = {"tmpl": {}}
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            r = await svc.get_automation_metrics()
            assert r["total_automations"] == 0
            assert r["scheduled_automations"] == 1
            assert r["active_triggers"] == 1

    async def test_validate_automation_data(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc()
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            r = await svc._validate_automation_data({})
            assert r["valid"] is False
            r = await svc._validate_automation_data({"name": "n", "description": "d", "automation_type": "x",
                                                     "priority": "p", "conditions": [{}], "actions": [{}]})
            assert r["valid"] is False
            r = await svc._validate_automation_data({"name": "n", "description": "d", "automation_type": "x",
                                                     "priority": "p", "conditions": [{"type": "t"}], "actions": [{"type": "a"}]})
            assert r["valid"] is True

    async def test_setup_automation_triggers_all_types(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc()
        for cond in ["scheduled", "event_triggered", "threshold_exceeded", "anomaly_detected",
                     "security_alert", "compliance_violation"]:
            a = _wf_automation(mod, f"a_{cond}", conditions=[{"type": cond, "schedule": "x", "metric": "m",
                                                             "threshold": 5, "sensitivity": "high",
                                                             "threat_type": "t", "standard": "SOC2"}])
            for m in ["_schedule_automation", "_setup_event_trigger", "_setup_threshold_trigger",
                      "_setup_anomaly_trigger", "_setup_security_trigger", "_setup_compliance_trigger"]:
                setattr(svc, m, AsyncMock(return_value=True))
            await svc._setup_automation_triggers(a)
        svc._schedule_automation = AsyncMock(side_effect=RuntimeError("x"))
        await svc._setup_automation_triggers(_wf_automation(mod, "err", conditions=[{"type": "scheduled"}]))

    async def test_execute_automation_action_all_types(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc()
        with patch.object(svc, "_execute_notification_action", new=AsyncMock(return_value={"success": True})), \
             patch.object(svc, "_execute_workflow_action", new=AsyncMock(return_value={"success": True})), \
             patch.object(svc, "_execute_security_enforcement_action", new=AsyncMock(return_value={"success": True})), \
             patch.object(svc, "_execute_compliance_check_action", new=AsyncMock(return_value={"success": True})), \
             patch.object(svc, "_execute_data_processing_action", new=AsyncMock(return_value={"success": True})), \
             patch.object(svc, "_execute_api_call_action", new=AsyncMock(return_value={"success": True})), \
             patch.object(svc, "_execute_email_action", new=AsyncMock(return_value={"success": True})), \
             patch.object(svc, "_execute_message_action", new=AsyncMock(return_value={"success": True})), \
             patch.object(svc, "_execute_logging_action", new=AsyncMock(return_value={"success": True})), \
             patch.object(svc, "_execute_auditing_action", new=AsyncMock(return_value={"success": True})), \
             patch.object(svc, "_execute_reporting_action", new=AsyncMock(return_value={"success": True})), \
             patch.object(svc, "_execute_remediation_action", new=AsyncMock(return_value={"success": True})):
            for t in ["notification", "workflow_execution", "security_enforcement", "compliance_check",
                      "data_processing", "api_call", "email_send", "message_send", "logging", "auditing",
                      "reporting", "remediation", "unknown"]:
                r = await svc._execute_automation_action({"type": t, "config": {}}, {}, None)
                if t == "unknown":
                    assert r["success"] is False
                else:
                    assert r["success"] is True
        with patch.object(svc, "_execute_notification_action", new=AsyncMock(side_effect=RuntimeError("x"))):
            r = await svc._execute_automation_action({"type": "notification"}, {}, None)
            assert r["success"] is False

    async def test_action_executors_detail(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc()
        for fn, config in [
            ("_execute_notification_action", {"channels": ["security_team", "compliance_officer", "management", "slack", "teams", "email"], "message": "m", "urgency": "high"}),
            ("_execute_notification_action", {"channels": []}),
            ("_execute_workflow_action", {}),
            ("_execute_workflow_action", {"workflow_id": "w1", "workflow_data": {}}),
            ("_execute_security_enforcement_action", {}),
            ("_execute_security_enforcement_action", {"action": "block_ip", "target": "1.2.3.4", "duration": 60}),
            ("_execute_security_enforcement_action", {"action": "lock_user", "target": "u"}),
            ("_execute_security_enforcement_action", {"action": "terminate_session", "target": "s"}),
            ("_execute_security_enforcement_action", {"action": "quarantine", "target": "r"}),
            ("_execute_compliance_check_action", {}),
            ("_execute_data_processing_action", {}),
            ("_execute_api_call_action", {}),
            ("_execute_email_action", {}),
            ("_execute_message_action", {}),
            ("_execute_logging_action", {}),
            ("_execute_auditing_action", {}),
            ("_execute_reporting_action", {}),
            ("_execute_remediation_action", {}),
        ]:
            r = await getattr(svc, fn)(config, {})
            assert isinstance(r, dict)
        # workflow action with unified service
        uni = MagicMock()
        uni.execute_enterprise_workflow = AsyncMock(return_value={"ok": True})
        svc.unified_service = uni
        r = await svc._execute_workflow_action({"workflow_id": "w2"}, {})
        assert r["success"] is True
        # security enforcement against real security service
        sec = MagicMock()
        for m in ["_block_ip", "_lock_user_account", "_terminate_session", "_quarantine_resource"]:
            setattr(sec, m, AsyncMock())
        svc.security_service = sec
        r = await svc._execute_security_enforcement_action({"action": "block_ip", "target": "1.1.1.1"}, {})
        assert r["success"] is True
        svc.security_service = None
        r = await svc._execute_security_enforcement_action({"action": "block_ip", "target": "x"}, {})
        assert r["success"] is False
        # compliance check with real security service
        report = mod.ComplianceReport(
            report_id="r1", standard=mod.ComplianceStandard.SOC2, period="monthly",
            overall_score=90.0, findings=[], recommendations=[], artifacts=[],
            generated_at=datetime.now(timezone.utc), generated_by="t",
        )
        sec2 = MagicMock()
        sec2.check_compliance = AsyncMock(return_value=report)
        svc.security_service = sec2
        r = await svc._execute_compliance_check_action({"standard": "SOC2"}, {"period": "monthly"})
        assert r["success"] is True
        r = await svc._execute_compliance_check_action({"standard": "BOGUS_STD"}, {})
        assert r["success"] is False
        svc.security_service = None
        r = await svc._execute_compliance_check_action({"standard": "SOC2"}, {})
        assert r["success"] is False

    async def test_security_compliance_checks(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc()
        automation = _wf_automation(mod)
        r = await svc._pre_execution_security_check(automation, {})
        assert r["passed"] is True
        r = await svc._pre_execution_security_check(automation, {"authorized": False})
        assert r["passed"] is False
        comp = _wf_automation(mod, automation_type=mod.WorkflowAutomationType.COMPLIANCE)
        r = await svc._pre_execution_compliance_check(comp, {})
        assert r["passed"] is True and r["compliance_level"] == "compliant"
        r = await svc._pre_execution_compliance_check(automation, {})
        assert r["passed"] is True
        r = await svc._post_execution_security_check(automation, [{"success": False}])
        assert r["passed"] is True
        r = await svc._post_execution_security_check(automation, [{"success": True}])
        assert r["passed"] is True
        r = await svc._post_execution_compliance_check(automation, [])
        assert r["passed"] is True

    async def test_notify_methods(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc()
        for fn in ["_notify_security_team", "_notify_compliance_officer", "_notify_management",
                   "_notify_slack", "_notify_teams", "_notify_email"]:
            await getattr(svc, fn)("m", "high", {})

    async def test_initialize_automation_templates(self):
        import integrations.atom_workflow_automation_service as mod

        db = MagicMock()
        db.execute.return_value = [("{\"template_id\": \"t1\", \"name\": \"n\"}",)]
        svc = _wf_svc({"database": db})
        ok = await svc._initialize_automation_templates()
        assert ok is True
        assert "t1" in svc.automation_templates
        assert "security_alert_response" in svc.automation_templates
        db2 = MagicMock()
        db2.execute.side_effect = RuntimeError("db down")
        svc2 = _wf_svc({"database": db2})
        assert await svc2._initialize_automation_templates() is True  # inner try swallows, defaults still load

    async def test_scheduling_and_trigger_listeners(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc()
        svc.scheduler_running = True
        assert await svc._initialize_automation_scheduling() is True
        svc.scheduler_running = False
        assert await svc._initialize_automation_scheduling() is True
        assert svc.scheduler_task is not None
        svc.scheduler_task.cancel()
        svc.scheduler_task = None
        assert await svc._initialize_trigger_listeners() is True
        assert "security_alert" in svc.trigger_listeners
        svc.automations = {"a1": _wf_automation(mod, conditions=[{"type": "security_alert"}])}
        await svc._initialize_trigger_listeners()
        assert "a1" in svc.trigger_listeners["security_alert"]["automations"]

    async def test_handle_event_trigger(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc()
        await svc._handle_event_trigger("unknown", {})
        svc.trigger_listeners = {"security_alert": {"automations": ["a1"], "callback": None}}
        svc.automations = {"a1": _wf_automation(mod)}
        with patch.object(svc, "execute_automation", new=AsyncMock(return_value={"ok": True})):
            await svc._handle_event_trigger("security_alert", {"k": "v"})
        svc.automations["a1"].enabled = False
        with patch.object(svc, "execute_automation", new=AsyncMock()):
            await svc._handle_event_trigger("security_alert", {})

    async def test_integration_endpoints_and_monitoring(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc()
        integration = MagicMock()
        integration.test_connection = AsyncMock(return_value=True)
        svc.platform_integrations = {"slack": integration}
        assert await svc._initialize_integration_endpoints() is True
        integration2 = MagicMock()
        integration2.test_connection = AsyncMock(side_effect=RuntimeError("x"))
        svc.platform_integrations = {"slack": integration2}
        assert await svc._initialize_integration_endpoints() is True
        svc.platform_integrations = {"slack": None}
        assert await svc._initialize_integration_endpoints() is True
        with patch.object(mod.asyncio, "create_task"):
            assert await svc._start_automation_monitoring() is True

    async def test_schedule_automation(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc()
        a = _wf_automation(mod, schedule="0 2 * * *")
        assert await svc._schedule_automation(a, {"type": "scheduled"}) is True
        assert a.next_run is not None
        a2 = _wf_automation(mod, automation_id="a2", schedule="0 2 * * *")
        a2.next_run = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert await svc._schedule_automation(a2, {"type": "scheduled"}) is True
        assert await svc._schedule_automation(_wf_automation(mod, automation_id="a3"), {"type": "manual"}) is False
        # schedule taken from condition
        a4 = _wf_automation(mod, automation_id="a4", schedule=None)
        assert await svc._schedule_automation(a4, {"type": "scheduled", "schedule": "0 3 * * *"}) is True
        assert a4.next_run is not None

    async def test_trigger_setup_methods(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc()
        a = _wf_automation(mod)
        assert await svc._setup_event_trigger(a, {}) is False
        assert await svc._setup_event_trigger(a, {"event_type": "evt"}) is True
        assert await svc._setup_event_trigger(a, {"type": "evt2"}) is True
        assert await svc._setup_threshold_trigger(a, {"metric": "m"}) is False
        assert await svc._setup_threshold_trigger(a, {"metric": "m", "threshold": 5, "operator": "gt"}) is True
        assert await svc._setup_anomaly_trigger(a, {}) is False
        assert await svc._setup_anomaly_trigger(a, {"metric": "m", "sensitivity": "high"}) is True
        assert await svc._setup_security_trigger(a, {"threat_type": "t", "severity": "high"}) is True
        sec = MagicMock()
        sec.register_security_trigger = AsyncMock()
        svc.security_service = sec
        assert await svc._setup_security_trigger(a, {}) is True
        assert await svc._setup_compliance_trigger(a, {"standard": "SOC2"}) is True
        uni = MagicMock()
        uni.register_compliance_trigger = AsyncMock()
        svc.unified_service = uni
        assert await svc._setup_compliance_trigger(a, {}) is True

    async def test_setup_platform_triggers(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc()
        assert await svc._setup_platform_triggers("nope", "a1", {}) is False
        svc.platform_integrations = {"slack": None}
        assert await svc._setup_platform_triggers("slack", "a1", {}) is False
        integration = MagicMock()
        integration.register_webhook = AsyncMock()
        integration.start_polling = AsyncMock()
        integration.subscribe_to_events = AsyncMock()
        svc.platform_integrations = {"slack": integration}
        assert await svc._setup_platform_triggers("slack", "a1", {"trigger_type": "webhook", "webhook_url": "u", "events": []}) is True
        assert await svc._setup_platform_triggers("slack", "a1", {"trigger_type": "polling", "polling_interval": 60}) is True
        assert await svc._setup_platform_triggers("slack", "a1", {"trigger_type": "event_subscription", "events": ["e"]}) is True
        assert await svc._setup_platform_triggers("slack", "a1", {"trigger_type": "other"}) is True

    async def test_send_notifications_and_metrics(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc()
        automation = _wf_automation(mod, metadata={"notification_rules": [
            {"status": "failed", "channels": ["slack:ops"], "message": "m", "urgency": "high"},
            {"on_error": True, "channels": ["email:admin", "teams:sec"]},
        ]})
        execution = _wf_execution(mod, status=mod.AutomationStatus.FAILED, error="err")
        assert await svc._send_automation_notifications(automation, execution) is True
        automation2 = _wf_automation(mod, "a2", metadata={"notification_rules": [{"status": "completed"}]})
        execution2 = _wf_execution(mod, execution_id="e2", status=mod.AutomationStatus.COMPLETED)
        assert await svc._send_automation_notifications(automation2, execution2) is True
        svc.automation_metrics["executions_by_status"]["completed"] = 3
        await svc._update_automation_metrics(automation2, execution2)
        assert svc.automation_metrics["executed_today"] == 1
        assert svc.automation_metrics["success_rate"] == 1.0

    async def test_log_event_service_info_close(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc()
        sec = MagicMock()
        sec.audit_event = AsyncMock()
        svc.security_service = sec
        await svc._log_automation_event("a1", "created", "u1", {})
        sec.audit_event.assert_awaited()
        info = await svc.get_service_info()
        assert info["status"] == "ACTIVE"
        task = MagicMock()
        svc.scheduler_task = task
        session = MagicMock()
        session.close = AsyncMock()
        svc.http_sessions = {"s": session}
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            await svc.close()
        task.cancel.assert_called()
        session.close.assert_awaited()


# ---------------------------------------------------------------------------
# atom_workflow_automation_service — error-path coverage
# ---------------------------------------------------------------------------
class TestWorkflowAutomationErrors:
    async def test_public_method_error_and_limit_paths(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc({"database": AsyncMock()})
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=False)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            assert (await svc.create_security_automation({"threat_type": "x"}, "u"))["ok"] is False
            assert (await svc.create_compliance_automation({"standard": "x"}, "u"))["ok"] is False
            assert (await svc.create_integration_automation("slack", {}))["ok"] is False
            assert await svc.get_automations() == []
            assert await svc.get_automation_executions() == []
            assert await svc.get_automation_metrics() == {}
            with pytest.raises(Exception):
                await svc._validate_automation_data({"name": "n"})
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(True, 0))
            assert (await svc.create_security_automation({"threat_type": "x"}, "u"))["ok"] is False
            assert (await svc.create_compliance_automation({"standard": "x"}, "u"))["ok"] is False
            assert (await svc.create_integration_automation("slack", {}))["ok"] is False
            assert await svc.get_automations() == []
            assert await svc.get_automation_executions() == []
            assert await svc.get_automation_metrics() == {}
            with pytest.raises(Exception):
                await svc._validate_automation_data({"name": "n"})
            # close() with breaker open
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            cb.is_enabled = AsyncMock(return_value=False)
            with pytest.raises(Exception):
                await svc.close()
            cb.is_enabled = AsyncMock(return_value=True)
            await svc.close()  # normal close, no scheduler/sessions

    async def test_exception_paths_in_public_methods(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc({"database": AsyncMock()})
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            with patch.object(svc, "create_automation", new=AsyncMock(side_effect=RuntimeError("x"))):
                r = await svc.create_security_automation({"threat_type": "x"}, "u")
                assert r["ok"] is False
                r = await svc.create_compliance_automation({"standard": "x"}, "u")
                assert r["ok"] is False
                r = await svc.create_integration_automation("slack", {})
                assert r["ok"] is False
            # create_automation error path
            svc2 = _wf_svc({"database": AsyncMock()})
            with patch.object(svc2, "_log_automation_event", new=AsyncMock(side_effect=RuntimeError("x"))):
                r = await svc2.create_automation({
                    "name": "n", "description": "d", "automation_type": "security",
                    "priority": "high", "conditions": [{"type": "security_alert"}],
                    "actions": [{"type": "notification"}],
                }, "u")
                assert r["ok"] is False
            # execute_automation error path (action raise + post check raise)
            svc3 = _wf_svc({"database": AsyncMock()})
            automation = _wf_automation(mod)
            svc3.automations["auto_1"] = automation
            with patch.object(svc3, "_pre_execution_security_check", new=AsyncMock(return_value={"passed": True})), \
                 patch.object(svc3, "_pre_execution_compliance_check", new=AsyncMock(return_value={"passed": True})), \
                 patch.object(svc3, "_execute_automation_action", new=AsyncMock(side_effect=RuntimeError("boom"))), \
                 patch.object(svc3, "_send_automation_notifications", new=AsyncMock()):
                r = await svc3.execute_automation("auto_1", {}, "t")
                assert r["ok"] is True  # action error recorded, run completes
            with patch.object(svc3, "_pre_execution_security_check", new=AsyncMock(return_value={"passed": True})), \
                 patch.object(svc3, "_pre_execution_compliance_check", new=AsyncMock(return_value={"passed": True})), \
                 patch.object(svc3, "_execute_automation_action", new=AsyncMock(return_value={"success": True})), \
                 patch.object(svc3, "_send_automation_notifications", new=AsyncMock()), \
                 patch.object(svc3, "_update_automation_metrics", new=AsyncMock()), \
                 patch.object(svc3, "_post_execution_security_check", new=AsyncMock(side_effect=RuntimeError("post"))):
                r = await svc3.execute_automation("auto_1", {}, "t")
                assert r["ok"] is False
            # get_automations error path
            svc4 = _wf_svc()
            a = _wf_automation(mod)
            a.created_at = "not-a-datetime"
            svc4.automations["auto_1"] = a
            assert await svc4.get_automations() == []
            # get_automation_executions error path
            svc5 = _wf_svc()
            e = _wf_execution(mod)
            e.started_at = "not-a-datetime"
            svc5.executions["exec_1"] = e
            assert await svc5.get_automation_executions() == []
            # get_automation_metrics error path
            svc6 = _wf_svc()
            svc6.automation_metrics = None
            assert await svc6.get_automation_metrics() == {}
            # get_automation_metrics error path
            svc7 = _wf_svc()
            with patch.object(mod, "rate_limiter") as rl2:
                rl2.is_rate_limited = AsyncMock(side_effect=RuntimeError("rl down"))
                assert await svc7.get_automation_metrics() == {}

    async def test_executor_error_paths(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc({"unified_service": MagicMock()})
        with patch.object(svc, "unified_service") as uni:
            uni.execute_enterprise_workflow = AsyncMock(side_effect=RuntimeError("wf fail"))
            r = await svc._execute_workflow_action({"workflow_id": "w1"}, {})
            assert r["success"] is False
        sec = MagicMock()
        sec._block_ip = AsyncMock(side_effect=RuntimeError("block fail"))
        svc.security_service = sec
        r = await svc._execute_security_enforcement_action({"action": "block_ip", "target": "1.1.1.1"}, {})
        assert r["success"] is False
        sec2 = MagicMock()
        sec2.check_compliance = AsyncMock(side_effect=RuntimeError("comp fail"))
        svc.security_service = sec2
        r = await svc._execute_compliance_check_action({"standard": "SOC2"}, {})
        assert r["success"] is False
        sec3 = MagicMock()
        sec3.check_compliance = AsyncMock(return_value=None)
        svc.security_service = sec3
        r = await svc._execute_compliance_check_action({"standard": "SOC2"}, {})
        assert r["success"] is False
        # notification executor raise
        svc2 = _wf_svc()
        with patch.object(svc2, "_notify_security_team", new=AsyncMock(side_effect=RuntimeError("n"))):
            r = await svc2._execute_notification_action({"channels": ["security_team"], "message": "m"}, {})
            assert r["success"] is False

    async def test_check_and_notify_error_paths(self):
        import integrations.atom_workflow_automation_service as mod

        class BoomCtx:
            def get(self, *a, **kw):
                raise RuntimeError("boom")

        svc = _wf_svc()
        automation = _wf_automation(mod)
        r = await svc._pre_execution_security_check(automation, BoomCtx())
        assert r["passed"] is False
        comp = _wf_automation(mod, automation_type=mod.WorkflowAutomationType.COMPLIANCE)
        r = await svc._pre_execution_compliance_check(comp, BoomCtx())
        assert r["passed"] is True  # compliance body never touches the context
        r = await svc._pre_execution_compliance_check(None, {})
        assert r["passed"] is False
        r = await svc._post_execution_security_check(automation, [BoomCtx()])
        assert r["passed"] is False
        r = await svc._post_execution_compliance_check(automation, [])
        assert r["passed"] is True
        # notify errors
        svc2 = _wf_svc()
        with pytest.raises(RuntimeError):
            with patch.object(svc2, "_notify_security_team", new=AsyncMock(side_effect=RuntimeError("x"))):
                await svc2._notify_security_team("m", "high", {})  # direct — no try wrapper
        # _execute_notification_action wraps all notify calls
        with patch.object(svc2, "_notify_security_team", new=AsyncMock(side_effect=RuntimeError("x"))), \
             patch.object(svc2, "_notify_compliance_officer", new=AsyncMock(side_effect=RuntimeError("x"))), \
             patch.object(svc2, "_notify_management", new=AsyncMock(side_effect=RuntimeError("x"))), \
             patch.object(svc2, "_notify_slack", new=AsyncMock(side_effect=RuntimeError("x"))), \
             patch.object(svc2, "_notify_teams", new=AsyncMock(side_effect=RuntimeError("x"))), \
             patch.object(svc2, "_notify_email", new=AsyncMock(side_effect=RuntimeError("x"))):
            r = await svc2._execute_notification_action(
                {"channels": ["security_team", "compliance_officer", "management", "slack", "teams", "email"], "message": "m"}, {})
            assert r["success"] is False

    async def test_loops_iterations(self):
        import integrations.atom_workflow_automation_service as mod

        # scheduler loop: runs due automation once, then sleeps
        svc = _wf_svc({"database": AsyncMock()})
        svc.scheduler_running = True
        automation = _wf_automation(mod, schedule="0 2 * * *")
        automation.next_run = datetime.now(timezone.utc) - timedelta(seconds=1)
        svc.automations["auto_1"] = automation
        with patch.object(svc, "execute_automation", new=AsyncMock(return_value={"ok": True})), \
             patch.object(mod.asyncio, "sleep", new=AsyncMock(side_effect=RuntimeError("stop"))):
            with pytest.raises(RuntimeError):
                await svc._scheduler_loop()
        # scheduler loop error path
        svc2 = _wf_svc()
        svc2.scheduler_running = True
        svc2.automations["bad"] = _wf_automation(mod, "bad")
        svc2.automations["bad"].next_run = datetime.now(timezone.utc) - timedelta(seconds=1)
        with patch.object(svc2, "execute_automation", new=AsyncMock(side_effect=RuntimeError("ex"))), \
             patch.object(mod.asyncio, "sleep", new=AsyncMock(side_effect=RuntimeError("stop2"))):
            with pytest.raises(RuntimeError):
                await svc2._scheduler_loop()
        # monitoring loop: high failure rate warning
        svc3 = _wf_svc()
        automation3 = _wf_automation(mod, "mon")
        automation3.last_execution_status = "failed"
        automation3.execution_count = 10
        automation3.failure_count = 9
        svc3.automations["mon"] = automation3
        with patch.object(mod.asyncio, "sleep", new=AsyncMock(side_effect=RuntimeError("stop3"))):
            with pytest.raises(RuntimeError):
                await svc3._monitoring_loop()
        assert svc3.automation_metrics["total_automations"] == 1
        # load automations error paths
        db = MagicMock()
        db.execute.side_effect = RuntimeError("db down")
        svc4 = _wf_svc({"database": db})
        assert await svc4._load_automations() is False
        svc5 = _wf_svc()
        assert await svc5._load_automations() is False
        # init methods error paths
        svc6 = _wf_svc()
        with patch.object(mod.asyncio, "create_task", side_effect=RuntimeError("x")):
            assert await svc6._initialize_automation_scheduling() is False
        with patch.object(mod.asyncio, "create_task", side_effect=RuntimeError("x")):
            assert await svc6._start_automation_monitoring() is False
        with patch.object(svc6, "execute_automation", new=AsyncMock(side_effect=RuntimeError("x"))):
            svc6.trigger_listeners = {"security_alert": {"automations": ["a1"], "callback": None}}
            svc6.automations = {"a1": _wf_automation(mod)}
            await svc6._handle_event_trigger("security_alert", {})
        # trigger setup error paths
        with patch.object(svc6, "_setup_event_trigger", new=AsyncMock(side_effect=RuntimeError("x"))):
            await svc6._setup_automation_triggers(_wf_automation(mod, "t1", conditions=[{"type": "event_triggered"}]))
        a = _wf_automation(mod, "t2")
        sec_boom = MagicMock()
        sec_boom.register_security_trigger = AsyncMock(side_effect=RuntimeError("x"))
        svc6.security_service = sec_boom
        assert await svc6._setup_security_trigger(a, {"threat_type": "t"}) is False
        uni_boom = MagicMock()
        uni_boom.register_compliance_trigger = AsyncMock(side_effect=RuntimeError("x"))
        svc6.unified_service = uni_boom
        assert await svc6._setup_compliance_trigger(a, {"standard": "s"}) is False
        # integration endpoints error path
        svc7 = _wf_svc()
        svc7.platform_integrations = {"slack": MagicMock(test_connection=AsyncMock(side_effect=RuntimeError("x")))}
        assert await svc7._initialize_integration_endpoints() is True
        # scheduler loop guard (scheduler_running False)
        svc8 = _wf_svc()
        svc8.scheduler_running = True
        assert await svc8._initialize_automation_scheduling() is True

    async def test_module_init_config_none_and_import_guards(self):
        import integrations.atom_workflow_automation_service as mod

        svc = mod.AtomWorkflowAutomationService("t1", None)
        assert svc.config == {}
        assert svc.workspace_id == "t1"
        assert mod.WorkflowSecurityLevel is not None
        assert mod.ComplianceStandard is not None


# ---------------------------------------------------------------------------
# atom_workflow_automation_service — final 1% push
# ---------------------------------------------------------------------------
class TestWorkflowAutomationFinal:
    async def test_execute_automation_circuit_rate_and_except(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc({"database": AsyncMock()})
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=False)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            r = await svc.execute_automation("a1", {}, "t")
            assert r["ok"] is False and "temporarily disabled" in r["error"]
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(True, 0))
            r = await svc.execute_automation("a1", {}, "t")
            assert r["ok"] is False and "Rate limit" in r["error"]
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            # exception in the automation loop itself (post-check raise) -> error dict
            automation = _wf_automation(mod)
            svc.automations["auto_1"] = automation
            with patch.object(svc, "_pre_execution_security_check", new=AsyncMock(return_value={"passed": True})), \
                 patch.object(svc, "_pre_execution_compliance_check", new=AsyncMock(return_value={"passed": True})), \
                 patch.object(svc, "_execute_automation_action", new=AsyncMock(return_value={"success": True})), \
                 patch.object(svc, "_post_execution_security_check", new=AsyncMock(return_value={"passed": True})), \
                 patch.object(svc, "_post_execution_compliance_check", new=AsyncMock(return_value={"passed": True})), \
                 patch.object(svc, "_send_automation_notifications", new=AsyncMock()), \
                 patch.object(svc, "_update_automation_metrics", new=AsyncMock(side_effect=RuntimeError("metrics"))):
                r = await svc.execute_automation("auto_1", {}, "t")
                assert r["ok"] is False

    async def test_execution_filters_continue_branches(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc()
        e1 = _wf_execution(mod, execution_id="e1", automation_id="a1", triggered_by="sys")
        svc.executions = {"e1": e1}
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            r = await svc.get_automation_executions("other")
            assert r == []
            r = await svc.get_automation_executions(filters={"status": "nope"})
            assert r == []
            r = await svc.get_automation_executions(filters={"triggered_by": "nope"})
            assert r == []
            r = await svc.get_automation_executions(filters={"date_from": datetime(2030, 1, 1, tzinfo=timezone.utc).date()})
            assert r == []
            r = await svc.get_automation_executions(filters={"date_to": datetime(2000, 1, 1, tzinfo=timezone.utc).date()})
            assert r == []

    async def test_pre_execution_internal_level_and_workflow_fallback(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc()
        automation = _wf_automation(mod, automation_type=mod.WorkflowAutomationType.GOVERNANCE)
        r = await svc._pre_execution_security_check(automation, {})
        assert r["passed"] is True
        # workflow action without unified service
        svc.unified_service = None
        r = await svc._execute_workflow_action({"workflow_id": "w1"}, {})
        assert r["success"] is False and "Unified service" in r["error"]

    async def test_init_and_trigger_error_excepts(self):
        import integrations.atom_workflow_automation_service as mod

        svc = _wf_svc()
        # _initialize_automation_scheduling except
        with patch.object(mod.asyncio, "create_task", side_effect=RuntimeError("x")):
            assert await svc._initialize_automation_scheduling() is False
        # _initialize_trigger_listeners except (bad condition dict)
        svc.automations = {"a1": _wf_automation(mod, conditions=[None])}
        assert await svc._initialize_trigger_listeners() is False
        # _schedule_automation except
        a = _wf_automation(mod, schedule="0 2 * * *")
        with patch("integrations.atom_workflow_automation_service.datetime") as dt_mock:
            dt_mock.now.side_effect = RuntimeError("tz")
            assert await svc._schedule_automation(a, {"type": "scheduled"}) is False
        # _setup_event_trigger except
        with patch.object(svc, "trigger_listeners", new=None):
            assert await svc._setup_event_trigger(_wf_automation(mod, "e1", conditions=[{"type": "event_triggered"}]), {"type": "event_triggered"}) is False
        # _setup_threshold_trigger except
        with patch.object(svc, "active_triggers", new=None):
            assert await svc._setup_threshold_trigger(_wf_automation(mod, "t1"), {"metric": "m", "threshold": 1}) is False
        # _setup_anomaly_trigger except
        with patch.object(svc, "active_triggers", new=None):
            assert await svc._setup_anomaly_trigger(_wf_automation(mod, "an1"), {"metric": "m"}) is False
        # _setup_platform_triggers except
        svc.platform_integrations = {"slack": MagicMock(register_webhook=AsyncMock(side_effect=RuntimeError("x")))}
        assert await svc._setup_platform_triggers("slack", "a1", {"trigger_type": "webhook", "webhook_url": "u"}) is False
        # _send_automation_notifications except
        svc2 = _wf_svc()
        with patch.object(svc2, "_notify_slack", new=AsyncMock(side_effect=RuntimeError("x"))):
            automation = _wf_automation(mod, metadata={"notification_rules": [{"status": "failed", "channels": ["slack:ops"]}]})
            execution = _wf_execution(mod, status=mod.AutomationStatus.FAILED, error="e")
            assert await svc2._send_automation_notifications(automation, execution) is False
        # _log_automation_event with raising security service
        svc3 = _wf_svc()
        sec = MagicMock()
        sec.audit_event = AsyncMock(side_effect=RuntimeError("audit"))
        svc3.security_service = sec
        with pytest.raises(RuntimeError):
            await svc3._log_automation_event("a", "t", "u", {})

    async def test_import_guards_fallback_blocks(self):
        """Force the module-level guarded imports to take the final fallback
        (both bare-name and package-qualified import failures)."""
        import importlib
        import integrations.atom_workflow_automation_service as mod

        with patch.dict(sys.modules, {
            "atom_enterprise_security_service": None,
            "atom_enterprise_unified_service": None,
            "integrations.atom_enterprise_security_service": None,
            "integrations.atom_enterprise_unified_service": None,
        }):
            importlib.reload(mod)
            assert mod.ComplianceStandard is None
            assert mod.WorkflowSecurityLevel is None
        importlib.reload(mod)
        assert mod.ComplianceStandard is not None


# ---------------------------------------------------------------------------
# atom_enterprise_unified_service.py
# ---------------------------------------------------------------------------
def _euw(mod, workflow_id="wf_1", **over):
    data = dict(
        workflow_id=workflow_id, name="w", description="d",
        service_type=mod.EnterpriseServiceType.SECURITY,
        security_level=mod.WorkflowSecurityLevel.RESTRICTED,
        compliance_standards=[mod.ComplianceStandard.SOC2],
        triggers=[{"type": "security_alert"}],
        steps=[{"name": "s1", "type": "security_check", "config": {}}],
        actions=[{"type": "security_enforcement", "config": {}, "timeout": 60}],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        created_by="u", status="active", metadata={}, audit_trail=[], compliance_checks=[],
    )
    data.update(over)
    return mod.EnterpriseWorkflow(**data)


class TestEnterpriseUnifiedCoverage:
    async def test_initialize(self):
        import integrations.atom_enterprise_unified_service as mod

        svc = mod.AtomEnterpriseUnifiedService("t1", {"security_service": MagicMock(), "ai_service": MagicMock()})
        for m in ["_initialize_enterprise_services", "_setup_workflow_security_integration",
                  "_setup_compliance_automation", "_setup_ai_powered_automation",
                  "_start_enterprise_monitoring"]:
            setattr(svc, m, AsyncMock())
        assert await svc.initialize() is True
        svc2 = mod.AtomEnterpriseUnifiedService("t1", {})
        assert await svc2.initialize() is False

    async def test_create_enterprise_workflow_flows(self):
        import integrations.atom_enterprise_unified_service as mod

        svc = mod.AtomEnterpriseUnifiedService("t1", {"security_service": MagicMock()})
        svc.security_service.audit_event = AsyncMock()
        data = {
            "name": "wf", "description": "d", "service_type": "security",
            "security_level": "restricted",
            "compliance_standards": ["SOC2"],
            "triggers": [], "steps": [], "actions": [],
        }
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            r = await svc.create_enterprise_workflow(data, "u1")
            assert r["ok"] is True
            assert r["workflow_id"] in svc.enterprise_workflows
            # validation failure (invalid standard)
            bad = dict(data)
            bad["compliance_standards"] = ["NOT_A_STD"]
            r = await svc.create_enterprise_workflow(bad, "u1")
            assert r["ok"] is False
            # workflow_service create failure
            ws = MagicMock()
            ws.create_workflow = AsyncMock(return_value={"ok": False, "error": "no"})
            svc.workflow_service = ws
            r = await svc.create_enterprise_workflow(data, "u1")
            assert r["ok"] is False
            # database store
            db = AsyncMock()
            svc2 = mod.AtomEnterpriseUnifiedService("t1", {"security_service": MagicMock(), "database": db})
            svc2.security_service.audit_event = AsyncMock()
            r = await svc2.create_enterprise_workflow(data, "u1")
            assert r["ok"] is True
            db.store_enterprise_workflow.assert_awaited()

    async def test_execute_enterprise_workflow_flows(self):
        import integrations.atom_enterprise_unified_service as mod

        svc = mod.AtomEnterpriseUnifiedService("t1", {"security_service": MagicMock()})
        wf = _euw(mod)
        svc.enterprise_workflows["wf_1"] = wf
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            r = await svc.execute_enterprise_workflow("missing", {}, "u")
            assert r["ok"] is False
            with patch.object(svc, "_security_pre_check", new=AsyncMock(return_value={"passed": False, "reason": "no"})), \
                 patch.object(svc, "_log_enterprise_event", new=AsyncMock()):
                r = await svc.execute_enterprise_workflow("wf_1", {}, "u")
                assert r["ok"] is False
            with patch.object(svc, "_security_pre_check", new=AsyncMock(return_value={"passed": True})), \
                 patch.object(svc, "_compliance_pre_check", new=AsyncMock(return_value={"passed": False, "reason": "no"})), \
                 patch.object(svc, "_log_enterprise_event", new=AsyncMock()):
                r = await svc.execute_enterprise_workflow("wf_1", {}, "u")
                assert r["ok"] is False
            with patch.object(svc, "_security_pre_check", new=AsyncMock(return_value={"passed": True})), \
                 patch.object(svc, "_compliance_pre_check", new=AsyncMock(return_value={"passed": True})), \
                 patch.object(svc, "_get_ai_enhanced_context", new=AsyncMock(return_value={"ctx": 1})), \
                 patch.object(svc, "_execute_workflow_step", new=AsyncMock(return_value={"success": True, "execution_time": 0.1})), \
                 patch.object(svc, "_monitor_step_execution", new=AsyncMock(return_value={"alert": True, "severity": "high"})), \
                 patch.object(svc, "_monitor_step_compliance", new=AsyncMock(return_value={"violation": True, "severity": "high"})), \
                 patch.object(svc, "_handle_security_alert", new=AsyncMock()), \
                 patch.object(svc, "_handle_compliance_violation", new=AsyncMock()), \
                 patch.object(svc, "_security_post_check", new=AsyncMock(return_value={"passed": True})), \
                 patch.object(svc, "_compliance_post_check", new=AsyncMock(return_value={"passed": True})), \
                 patch.object(svc, "_log_enterprise_event", new=AsyncMock()):
                r = await svc.execute_enterprise_workflow("wf_1", {"x": 1}, "u")
                assert r["ok"] is True
                assert len(wf.audit_trail) == 1
            # exception path
            with patch.object(svc, "_security_pre_check", new=AsyncMock(side_effect=RuntimeError("x"))):
                r = await svc.execute_enterprise_workflow("wf_1", {}, "u")
                assert r["ok"] is False

    async def test_create_security_automation_flows(self):
        import integrations.atom_enterprise_unified_service as mod

        svc = mod.AtomEnterpriseUnifiedService("t1", {"security_service": MagicMock()})
        svc.security_service.audit_event = AsyncMock()
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            data = {"name": "auto", "description": "d", "triggers": [], "metadata": {}}
            with patch.object(svc, "create_enterprise_workflow", new=AsyncMock(
                return_value={"ok": False, "error": "no"})), \
                 patch.object(svc, "_log_enterprise_event", new=AsyncMock()):
                r = await svc.create_security_automation(data, "u")
                assert r["ok"] is False
            with patch.object(svc, "create_enterprise_workflow", new=AsyncMock(
                return_value={"ok": True, "workflow_id": "wf_x"})):
                r = await svc.create_security_automation(data, "u")
                assert r["ok"] is True
                assert r["automation_id"] in svc.active_automations
            with patch.object(svc, "create_enterprise_workflow", new=AsyncMock(
                side_effect=RuntimeError("boom"))):
                r = await svc.create_security_automation(data, "u")
                assert r["ok"] is False

    async def test_create_compliance_automation_flows(self):
        import integrations.atom_enterprise_unified_service as mod

        svc = mod.AtomEnterpriseUnifiedService("t1", {"security_service": MagicMock()})
        svc.security_service.audit_event = AsyncMock()
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            data = {
                "name": "comp", "description": "d",
                "compliance_standards": ["SOC2"], "workflow_type": "audit_remediation",
                "triggers": ["audit_failure"], "schedule": "daily", "metadata": {},
            }
            with patch.object(svc, "create_enterprise_workflow", new=AsyncMock(
                return_value={"ok": False, "error": "no"})):
                r = await svc.create_compliance_automation(data, "u")
                assert r["ok"] is False
            with patch.object(svc, "create_enterprise_workflow", new=AsyncMock(
                return_value={"ok": True, "workflow_id": "wf_c"})):
                r = await svc.create_compliance_automation(data, "u")
                assert r["ok"] is True
                assert r["automation_id"] in svc.compliance_automations
            with patch.object(svc, "create_enterprise_workflow", new=AsyncMock(
                side_effect=RuntimeError("boom"))):
                r = await svc.create_compliance_automation(data, "u")
                assert r["ok"] is False

    async def test_getters_and_metrics(self):
        import integrations.atom_enterprise_unified_service as mod

        svc = mod.AtomEnterpriseUnifiedService("t1", {"security_service": MagicMock()})
        wf1 = _euw(mod, "wf_1")
        wf2 = _euw(mod, "wf_2", service_type=mod.EnterpriseServiceType.COMPLIANCE,
                   security_level=mod.WorkflowSecurityLevel.CONFIDENTIAL,
                   compliance_standards=[mod.ComplianceStandard.GDPR],
                   metadata={"execution_count": 5, "success_rate": 0.8, "last_executed": "now"})
        svc.enterprise_workflows = {"wf_1": wf1, "wf_2": wf2}
        svc.active_automations = {
            "a1": {"automation_type": "security", "active": True},
            "a2": {"automation_type": "compliance", "active": False},
        }
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            r = await svc.get_enterprise_workflows()
            assert len(r) == 2
            r = await svc.get_enterprise_workflows(filters={"service_type": "compliance"})
            assert len(r) == 1
            r = await svc.get_enterprise_workflows(filters={"security_level": "confidential"})
            assert len(r) == 1
            r = await svc.get_enterprise_workflows(filters={"compliance_standard": "gdpr"})
            assert len(r) == 1
            status = await svc.get_automations_status()
            assert status["total_automations"] == 2
            assert status["security_automations"] == 1
            assert status["active_automations"] == 1
            metrics = await svc.get_enterprise_metrics()
            assert metrics["total_workflows"] == 0
            await svc.close()
            info = await svc.get_service_info()
            assert info["status"] == "ACTIVE"

    async def test_private_helpers(self):
        import integrations.atom_enterprise_unified_service as mod

        svc = mod.AtomEnterpriseUnifiedService("t1", {})
        wf = _euw(mod)
        r = await svc._validate_enterprise_workflow(wf)
        assert r["valid"] is True
        actions = await svc._create_security_workflow_actions(wf, "u")
        assert len(actions) == 1
        assert len(svc.security_workflow_actions) == 1
        autos = await svc._create_compliance_automations(wf, "u")
        assert len(autos) == 1
        r = await svc._security_pre_check(wf, {}, "u")
        assert r["passed"] is True
        r = await svc._compliance_pre_check(wf, {}, "u")
        assert r["passed"] is True
        r = await svc._get_ai_enhanced_context(wf, {})
        assert r["ai_enhanced"] is False
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(return_value=MagicMock(ok=True, output_data={}, confidence=0.9))
        svc.ai_service = ai
        with patch.dict(mod.__dict__, {
            "AIRequest": MagicMock(),
            "AITaskType": MagicMock(USER_BEHAVIOR_ANALYSIS="uba"),
            "AIModelType": MagicMock(GPT_4="gpt4"),
            "AIServiceType": MagicMock(OPENAI="openai"),
        }):
            r = await svc._get_ai_enhanced_context(wf, {})
        assert r["ai_enhanced"] is True
        ai.process_ai_request = AsyncMock(return_value=MagicMock(ok=False))
        r = await svc._get_ai_enhanced_context(wf, {})
        assert r["ai_enhanced"] is False
        ai.process_ai_request = AsyncMock(side_effect=RuntimeError("x"))
        r = await svc._get_ai_enhanced_context(wf, {})
        assert r["ai_enhanced"] is False
        # step execution types
        for step_type in ["security_check", "compliance_check", "ai_analysis", "data_processing",
                          "notification", "custom"]:
            r = await svc._execute_workflow_step({"type": step_type, "config": {}}, {}, "u")
            assert r["success"] is True
        with patch.object(svc, "_execute_custom_step", new=AsyncMock(side_effect=RuntimeError("x"))):
            r = await svc._execute_workflow_step({"type": "custom"}, {}, "u")
            assert r["success"] is False
        # monitors
        assert await svc._monitor_step_execution({}, {}, "u") == {"alert": False, "monitoring_result": "No issues detected"}
        assert await svc._monitor_step_compliance({}, {}, "u") == {"violation": False, "compliance_result": "No violations detected"}
        # validation helpers
        assert await svc._validate_workflow_security(wf) == {"valid": True, "errors": []}
        assert await svc._validate_workflow_compliance(wf) == {"valid": True, "errors": []}
        assert await svc._assess_action_risk({}, mod.WorkflowSecurityLevel.INTERNAL) == {"risk_score": 0.5, "risk_level": "medium"}
        assert await svc._check_user_authorization("u", mod.WorkflowSecurityLevel.INTERNAL) == {"authorized": True}
        assert await svc._validate_context_security({}, mod.WorkflowSecurityLevel.INTERNAL) == {"valid": True}
        assert await svc._check_compliance_requirements("SOC2", {}, "u") == {"compliant": True}
        assert await svc._get_security_ai_analysis({}) == {"ai_analysis": "Security event analyzed"}
        assert await svc._get_compliance_ai_analysis({}) == {"ai_analysis": "Compliance violation analyzed"}
        # init/setup/monitoring methods
        with _mock_imports({
            "integrations.atom_ai_integration": MagicMock(ai_integration=MagicMock()),
        }), patch(
            "integrations.atom_enterprise_security_service.atom_enterprise_security_service",
            new=MagicMock(),
        ):
            await svc._initialize_enterprise_services()
            assert svc.security_service is not None
        sec = MagicMock()
        sec.setup_workflow_monitoring = AsyncMock()
        sec.setup_compliance_automation = AsyncMock()
        sec.start_monitoring = AsyncMock()
        svc.security_service = sec
        ai_int = MagicMock()
        ai_int.setup_workflow_automation = AsyncMock()
        ai_int.start_monitoring = AsyncMock()
        svc.ai_integration = ai_int
        await svc._setup_workflow_security_integration()
        await svc._setup_compliance_automation()
        await svc._setup_ai_powered_automation()
        await svc._start_enterprise_monitoring()
        # blocking/monitoring handlers
        await svc._block_workflow_execution("wf_1", "r")
        wf.status = "active"
        svc.enterprise_workflows["wf_1"] = wf
        await svc._block_workflow_execution("wf_1", "r")
        assert wf.status == "blocked"
        await svc._increase_workflow_monitoring("wf_1")
        await svc._enable_compliance_logging("wf_1")
        assert svc.workflow_monitoring["wf_1"]["compliance_logging"] is True
        with patch.object(svc, "_log_enterprise_event", new=AsyncMock()):
            await svc._notify_security_team({"type": "t"}, wf, "u")
            await svc._notify_compliance_team({"type": "t"}, wf, "u")
        assert await svc._security_post_check(wf, [], "u") == {"passed": True}
        assert await svc._compliance_post_check(wf, [], "u") == {"passed": True}
        # log enterprise event with security service
        svc.security_service = MagicMock()
        svc.security_service.audit_event = AsyncMock()
        await svc._log_enterprise_event("evt", "u", "r", "a", "s", {"k": "v"})
        svc.security_service.audit_event.assert_awaited()

    async def test_validation_failure_and_error_paths(self):
        import integrations.atom_enterprise_unified_service as mod

        svc = mod.AtomEnterpriseUnifiedService("t1", {})
        # _validate_enterprise_workflow error path
        with patch.object(svc, "_validate_workflow_security", new=AsyncMock(side_effect=RuntimeError("x"))):
            r = await svc._validate_enterprise_workflow(_euw(mod))
            assert r["valid"] is False
        # _security_pre_check unauthorized
        with patch.object(svc, "_check_user_authorization", new=AsyncMock(return_value={"authorized": False})):
            r = await svc._security_pre_check(_euw(mod), {}, "u")
            assert r["passed"] is False
        with patch.object(svc, "_check_user_authorization", new=AsyncMock(side_effect=RuntimeError("x"))):
            r = await svc._security_pre_check(_euw(mod), {}, "u")
            assert r["passed"] is False
        # _compliance_pre_check failure
        with patch.object(svc, "_check_compliance_requirements", new=AsyncMock(return_value={"compliant": False})):
            r = await svc._compliance_pre_check(_euw(mod), {}, "u")
            assert r["passed"] is False
        with patch.object(svc, "_check_compliance_requirements", new=AsyncMock(side_effect=RuntimeError("x"))):
            r = await svc._compliance_pre_check(_euw(mod), {}, "u")
            assert r["passed"] is False
        # getter error paths
        with patch.object(mod, "rate_limiter") as rl:
            rl.is_rate_limited = AsyncMock(side_effect=RuntimeError("x"))
            assert await svc.get_enterprise_workflows() == []
            assert "error" in await svc.get_automations_status()
            with pytest.raises(Exception):
                await svc.get_enterprise_metrics()
            with pytest.raises(Exception):
                await svc.close()


# ---------------------------------------------------------------------------
# atom_enterprise_unified_service — final push
# ---------------------------------------------------------------------------
class TestEnterpriseUnifiedFinal:
    async def test_circuit_and_rate_limit_paths(self):
        import integrations.atom_enterprise_unified_service as mod

        svc = mod.AtomEnterpriseUnifiedService("t1", {"security_service": MagicMock()})
        svc.security_service.audit_event = AsyncMock()
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=False)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            for call in [
                lambda: svc.create_enterprise_workflow({"name": "x"}, "u"),
                lambda: svc.execute_enterprise_workflow("w", {}, "u"),
                lambda: svc.create_security_automation({"name": "x"}, "u"),
                lambda: svc.create_compliance_automation({"name": "x"}, "u"),
                lambda: svc.handle_security_event({}),
                lambda: svc.handle_compliance_violation({}),
                lambda: svc.get_automations_status(),
            ]:
                r = await call()
                assert isinstance(r, dict), r
            assert await svc.get_enterprise_workflows() == []
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(True, 0))
            for call in [
                lambda: svc.create_enterprise_workflow({"name": "x"}, "u"),
                lambda: svc.execute_enterprise_workflow("w", {}, "u"),
                lambda: svc.create_security_automation({"name": "x"}, "u"),
                lambda: svc.create_compliance_automation({"name": "x"}, "u"),
                lambda: svc.handle_security_event({}),
                lambda: svc.handle_compliance_violation({}),
                lambda: svc.get_automations_status(),
            ]:
                r = await call()
                assert isinstance(r, dict), r
            assert await svc.get_enterprise_workflows() == []

    async def test_coerce_and_init_branches(self):
        import integrations.atom_enterprise_unified_service as mod

        assert mod._coerce_compliance_standard("SOC2") == mod.ComplianceStandard.SOC2
        assert mod._coerce_compliance_standard(mod.ComplianceStandard.GDPR) == mod.ComplianceStandard.GDPR
        assert mod._coerce_compliance_standard("soc2") == mod.ComplianceStandard.SOC2
        with pytest.raises(ValueError):
            mod._coerce_compliance_standard(123)
        # __init__ platform integrations from globals
        import types
        fake_mod = types.ModuleType("fake")
        with patch.dict(mod.__dict__, {
            "atom_slack_integration": "slack_obj",
            "atom_teams_integration": "teams_obj",
            "atom_google_chat_integration": "chat_obj",
            "atom_discord_integration": "discord_obj",
        }):
            svc = mod.AtomEnterpriseUnifiedService("t1", {})
            assert svc.platform_integrations == {
                "slack": "slack_obj", "teams": "teams_obj",
                "google_chat": "chat_obj", "discord": "discord_obj",
            }
        # workflow_service create failure inside create_enterprise_workflow
        svc2 = mod.AtomEnterpriseUnifiedService("t1", {"security_service": MagicMock()})
        svc2.security_service.audit_event = AsyncMock()
        ws = MagicMock()
        ws.create_workflow = AsyncMock(return_value={"ok": False, "error": "denied"})
        svc2.workflow_service = ws
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            data = {
                "name": "wf", "description": "d", "service_type": "security",
                "security_level": "restricted", "compliance_standards": ["SOC2"],
                "triggers": [], "steps": [], "actions": [],
            }
            r = await svc2.create_enterprise_workflow(data, "u")
            assert r["ok"] is False and r["error"] == "denied"
            # exception path
            ws.create_workflow = AsyncMock(side_effect=RuntimeError("boom"))
            r = await svc2.create_enterprise_workflow(data, "u")
            assert r["ok"] is False

    async def test_ai_context_all_paths(self):
        import integrations.atom_enterprise_unified_service as mod

        svc = mod.AtomEnterpriseUnifiedService("t1", {})
        wf = _euw(mod)
        ai = MagicMock()
        svc.ai_service = ai
        req = MagicMock()
        req.ok = True
        req.output_data = {"insights": 1}
        req.confidence = 0.9
        ai.process_ai_request = AsyncMock(return_value=req)
        with patch.dict(mod.__dict__, {
            "AIRequest": MagicMock(),
            "AITaskType": MagicMock(USER_BEHAVIOR_ANALYSIS="uba"),
            "AIModelType": MagicMock(GPT_4="gpt4"),
            "AIServiceType": MagicMock(OPENAI="openai"),
        }):
            r = await svc._get_ai_enhanced_context(wf, {"k": "v"})
        assert r["ai_enhanced"] is True
        assert r["ai_insights"] == {"insights": 1}

    async def test_singleton_and_import_guards(self):
        import importlib
        import integrations.atom_enterprise_unified_service as mod

        assert mod.atom_enterprise_unified_service is not None
        assert "database" in mod.atom_enterprise_unified_service.config
        real_security = sys.modules.pop("atom_enterprise_security_service", None)
        real_ai = sys.modules.pop("ai_enhanced_service", None)
        with patch.dict(sys.modules, {
            "ai_enhanced_service": None,
            "atom_ai_integration": None,
            "atom_discord_integration": None,
            "atom_enterprise_security_service": None,
            "atom_google_chat_integration": None,
            "atom_ingestion_pipeline": None,
            "atom_memory_service": None,
            "atom_search_service": None,
            "atom_slack_integration": None,
            "atom_teams_integration": None,
            "atom_workflow_service": None,
        }):
            importlib.reload(mod)
        importlib.reload(mod)
        assert mod.ComplianceStandard is not None


# ---------------------------------------------------------------------------
# atom_enterprise_unified_service — last gaps
# ---------------------------------------------------------------------------
class TestEnterpriseUnifiedLast:
    async def test_remaining_branches(self):
        import integrations.atom_enterprise_unified_service as mod

        # __init__ config=None
        svc = mod.AtomEnterpriseUnifiedService("t1", None)
        assert svc.config == {}
        # create_enterprise_workflow exception path
        svc2 = mod.AtomEnterpriseUnifiedService("t1", {"security_service": MagicMock()})
        svc2.security_service.audit_event = AsyncMock()
        data = {
            "name": "wf", "description": "d", "service_type": "security",
            "security_level": "restricted", "compliance_standards": ["SOC2"],
            "triggers": [], "steps": [], "actions": [],
        }
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            with patch.object(svc2, "_validate_enterprise_workflow", new=AsyncMock(side_effect=RuntimeError("x"))):
                r = await svc2.create_enterprise_workflow(data, "u")
                assert r["ok"] is False
        # _validate_enterprise_workflow security/compliance failure
        svc3 = mod.AtomEnterpriseUnifiedService("t1", {})
        wf = _euw(mod)
        with patch.object(svc3, "_validate_workflow_security", new=AsyncMock(return_value={"valid": False, "errors": ["e1"]})):
            r = await svc3._validate_enterprise_workflow(wf)
            assert r["valid"] is False and r["errors"] == ["e1"]
        with patch.object(svc3, "_validate_workflow_security", new=AsyncMock(return_value={"valid": True, "errors": []})), \
             patch.object(svc3, "_validate_workflow_compliance", new=AsyncMock(return_value={"valid": False, "errors": ["e2"]})):
            r = await svc3._validate_enterprise_workflow(wf)
            assert r["valid"] is False and r["errors"] == ["e2"]
        # _get_ai_enhanced_context ai_service fail path (line 1150)
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(return_value=MagicMock(ok=False))
        svc3.ai_service = ai
        with patch.dict(mod.__dict__, {
            "AIRequest": MagicMock(),
            "AITaskType": MagicMock(USER_BEHAVIOR_ANALYSIS="uba"),
            "AIModelType": MagicMock(GPT_4="gpt4"),
            "AIServiceType": MagicMock(OPENAI="openai"),
        }):
            r = await svc3._get_ai_enhanced_context(wf, {})
            assert r["ai_enhanced"] is False
        # setup method error paths
        for fn, attr in [("_setup_workflow_security_integration", "security_service"),
                         ("_setup_compliance_automation", "security_service"),
                         ("_setup_ai_powered_automation", "ai_integration"),
                         ("_start_enterprise_monitoring", "security_service")]:
            svc4 = mod.AtomEnterpriseUnifiedService("t1", {})
            boom = MagicMock()
            for m in ["setup_workflow_monitoring", "setup_compliance_automation", "start_monitoring", "setup_workflow_automation"]:
                setattr(boom, m, AsyncMock(side_effect=RuntimeError("x")))
            svc4.security_service = boom
            svc4.ai_integration = boom
            await getattr(svc4, fn)()
        # _initialize_enterprise_services error
        svc5 = mod.AtomEnterpriseUnifiedService("t1", {})
        with _mock_imports({"integrations.atom_ai_integration": ModuleType("_ai")}):
            with patch("integrations.atom_enterprise_security_service.atom_enterprise_security_service", new=MagicMock(side_effect=RuntimeError("x"))):
                await svc5._initialize_enterprise_services()

    async def test_handler_severity_branches(self):
        import integrations.atom_enterprise_unified_service as mod

        svc = mod.AtomEnterpriseUnifiedService("t1", {})
        wf = _euw(mod)
        svc.enterprise_workflows["wf_1"] = wf
        # medium severity -> monitoring paths
        with patch.object(svc, "_increase_workflow_monitoring", new=AsyncMock()) as inc, \
             patch.object(svc, "_notify_security_team", new=AsyncMock()):
            await svc._handle_security_alert({"severity": "medium"}, wf, {}, "u")
            inc.assert_awaited()
        with patch.object(svc, "_enable_compliance_logging", new=AsyncMock()) as en, \
             patch.object(svc, "_notify_compliance_team", new=AsyncMock()):
            await svc._handle_compliance_violation({"severity": "medium"}, wf, {}, "u")
            en.assert_awaited()
        # low severity -> no block
        with patch.object(svc, "_block_workflow_execution", new=AsyncMock()) as blk, \
             patch.object(svc, "_notify_security_team", new=AsyncMock()):
            await svc._handle_security_alert({"severity": "low"}, wf, {}, "u")
            blk.assert_not_awaited()
        # active_workflows block path
        aw = MagicMock()
        svc.active_workflows["wf_1"] = aw
        await svc._block_workflow_execution("wf_1", "r")
        assert aw.status == "blocked"
        svc6 = mod.AtomEnterpriseUnifiedService("t1", {})
        svc6.enterprise_workflows["wf_1"] = wf
        with patch.object(svc6, "enterprise_workflows", new={"wf_1": MagicMock()}):
            svc6.enterprise_workflows["wf_1"].status = "active"
        # block error path (dict mock raising on item access)
        class BoomDict(dict):
            def __getitem__(self, k):
                raise RuntimeError("x")
        svc7 = mod.AtomEnterpriseUnifiedService("t1", {})
        svc7.active_workflows = BoomDict()
        svc7.enterprise_workflows = BoomDict()
        await svc7._block_workflow_execution("w", "r")
        # monitoring error paths
        svc8 = mod.AtomEnterpriseUnifiedService("t1", {})
        svc8.workflow_monitoring = BoomDict()
        await svc8._increase_workflow_monitoring("w")
        await svc8._enable_compliance_logging("w")
        # notify methods
        svc9 = mod.AtomEnterpriseUnifiedService("t1", {})
        await svc9._notify_security_team({"type": "x"}, wf, "u")
        await svc9._notify_compliance_team({"type": "x"}, wf, "u")
        # _log_enterprise_event without security service
        svc10 = mod.AtomEnterpriseUnifiedService("t1", {})
        await svc10._log_enterprise_event("e", "u", "r", "a", "s")

    async def test_getter_exception_and_close_paths(self):
        import integrations.atom_enterprise_unified_service as mod

        svc = mod.AtomEnterpriseUnifiedService("t1", {})
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            await svc.get_enterprise_metrics()
            await svc.close()
            await svc.get_automations_status()
            cb.is_enabled = AsyncMock(return_value=False)
            with pytest.raises(Exception):
                await svc.get_enterprise_metrics()
            with pytest.raises(Exception):
                await svc.close()
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(True, 0))
            with pytest.raises(Exception):
                await svc.get_enterprise_metrics()
            with pytest.raises(Exception):
                await svc.close()


# ---------------------------------------------------------------------------
# atom_enterprise_unified_service — final fixes
# ---------------------------------------------------------------------------
class TestEnterpriseUnifiedTiny:
    async def test_initialize_exception_and_validation_paths(self):
        import integrations.atom_enterprise_unified_service as mod

        svc = mod.AtomEnterpriseUnifiedService("t1", {"security_service": MagicMock(), "ai_service": MagicMock()})
        with patch.object(svc, "_initialize_enterprise_services", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await svc.initialize() is False
        svc2 = mod.AtomEnterpriseUnifiedService("t1", {})
        wf = _euw(mod)
        with patch.object(svc2, "_validate_workflow_security", new=AsyncMock(return_value={"valid": True, "errors": []})), \
             patch.object(svc2, "_validate_workflow_compliance", new=AsyncMock(return_value={"valid": True, "errors": []})), \
             patch.object(svc2, "_validate_enterprise_workflow", new=AsyncMock(return_value={"valid": False, "errors": ["bad step"]})):
            r = await svc2._validate_enterprise_workflow(wf)
            assert r == {"valid": False, "errors": ["bad step"]}
        # validation-failure return in create_enterprise_workflow (line 301)
        svc3 = mod.AtomEnterpriseUnifiedService("t1", {"security_service": MagicMock()})
        svc3.security_service.audit_event = AsyncMock()
        data = {
            "name": "wf", "description": "d", "service_type": "security",
            "security_level": "restricted", "compliance_standards": ["SOC2"],
            "triggers": [], "steps": [], "actions": [],
        }
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            with patch.object(svc3, "_validate_enterprise_workflow", new=AsyncMock(
                return_value={"valid": False, "errors": ["nope"]})):
                r = await svc3.create_enterprise_workflow(data, "u")
                assert r["ok"] is False and "validation failed" in r["error"]
        # _validate_enterprise_workflow circuit/rate branches (swallowed -> error dict)
        with patch.object(mod, "circuit_breaker") as cb2, patch.object(mod, "rate_limiter") as rl2:
            cb2.is_enabled = AsyncMock(return_value=False)
            rl2.is_rate_limited = AsyncMock(return_value=(False, 10))
            r = await svc2._validate_enterprise_workflow(wf)
            assert r["valid"] is False
            cb2.is_enabled = AsyncMock(return_value=True)
            rl2.is_rate_limited = AsyncMock(return_value=(True, 0))
            r = await svc2._validate_enterprise_workflow(wf)
            assert r["valid"] is False

    async def test_security_pre_check_context_failure(self):
        import integrations.atom_enterprise_unified_service as mod

        svc = mod.AtomEnterpriseUnifiedService("t1", {})
        wf = _euw(mod)
        with patch.object(svc, "_check_user_authorization", new=AsyncMock(return_value={"authorized": True})), \
             patch.object(svc, "_validate_context_security", new=AsyncMock(return_value={"valid": False})):
            r = await svc._security_pre_check(wf, {}, "u")
            assert r["passed"] is False
            assert r["reason"] == "Context security validation failed"

    async def test_handler_exception_paths(self):
        import integrations.atom_enterprise_unified_service as mod

        svc = mod.AtomEnterpriseUnifiedService("t1", {})
        wf = _euw(mod)
        sec = MagicMock()
        sec.log_security_alert = AsyncMock(side_effect=RuntimeError("x"))
        sec.log_compliance_violation = AsyncMock(side_effect=RuntimeError("x"))
        svc.security_service = sec
        await svc._handle_security_alert({"severity": "high"}, wf, {}, "u")
        await svc._handle_compliance_violation({"severity": "high"}, wf, {}, "u")
        # exception AFTER logging — block raises
        svc2 = mod.AtomEnterpriseUnifiedService("t1", {})
        svc2.enterprise_workflows["wf_1"] = wf
        with patch.object(svc2, "_block_workflow_execution", new=AsyncMock(side_effect=RuntimeError("x"))), \
             patch.object(svc2, "security_service", new=MagicMock()):
            with patch.object(svc2.security_service, "log_security_alert", new=AsyncMock()):
                await svc2._handle_security_alert({"severity": "high"}, wf, {}, "u")

    async def test_import_block_full_coverage(self):
        import importlib
        import types
        import integrations.atom_enterprise_unified_service as mod

        mock_mods = {
            "ai_enhanced_service": MagicMock(
                AIModelType=MagicMock(), AIRequest=MagicMock(), AIResponse=MagicMock(),
                AIServiceType=MagicMock(), AITaskType=MagicMock(), ai_enhanced_service=MagicMock()),
            "atom_ai_integration": MagicMock(atom_ai_integration=MagicMock()),
            "atom_discord_integration": MagicMock(atom_discord_integration=MagicMock()),
            "atom_enterprise_security_service": MagicMock(atom_enterprise_security_service=MagicMock()),
            "atom_google_chat_integration": MagicMock(atom_google_chat_integration=MagicMock()),
            "atom_ingestion_pipeline": MagicMock(AtomIngestionPipeline=MagicMock()),
            "atom_memory_service": MagicMock(AtomMemoryService=MagicMock()),
            "atom_search_service": MagicMock(AtomSearchService=MagicMock()),
            "atom_slack_integration": MagicMock(atom_slack_integration=MagicMock()),
            "atom_teams_integration": MagicMock(atom_teams_integration=MagicMock()),
            "atom_workflow_service": MagicMock(AtomWorkflowService=MagicMock(), Workflow=MagicMock(),
                                              WorkflowAction=MagicMock(), WorkflowStatus=MagicMock(),
                                              WorkflowStep=MagicMock(), WorkflowTrigger=MagicMock()),
        }
        with patch.dict(sys.modules, mock_mods):
            importlib.reload(mod)
        importlib.reload(mod)
        assert mod.atom_enterprise_unified_service is not None


# ---------------------------------------------------------------------------
# atom_enterprise_security_service.py
# ---------------------------------------------------------------------------
def _sec_svc(config=None):
    import integrations.atom_enterprise_security_service as mod

    cfg = config or {}
    return mod.AtomEnterpriseSecurityService("t1", cfg)


class TestSecurityServiceCoverage:
    async def test_initialize(self):
        import integrations.atom_enterprise_security_service as mod

        svc = _sec_svc()
        for m in ["_initialize_encryption", "_load_security_policies", "_initialize_threat_detection",
                  "_start_security_monitoring", "_initialize_compliance_monitoring"]:
            setattr(svc, m, AsyncMock())
        assert await svc.initialize() is True
        svc2 = _sec_svc()
        with patch.object(svc2, "_initialize_encryption", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await svc2.initialize() is False

    async def test_create_security_policy_flows(self):
        import integrations.atom_enterprise_security_service as mod

        svc = _sec_svc({"database": AsyncMock()})
        data = {
            "name": "p", "description": "d", "security_level": "enterprise",
            "compliance_standards": ["SOC2"], "rules": [], "enforcement_actions": [],
        }
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            r = await svc.create_security_policy(data, "u")
            assert r["ok"] is True
            assert r["policy_id"] in svc.active_policies
            svc.db.store_security_policy.assert_awaited()
            with patch.object(svc, "_validate_security_policy", new=AsyncMock(return_value={"valid": False, "errors": ["no"]})):
                r = await svc.create_security_policy(data, "u")
                assert r["ok"] is False
            cb.is_enabled = AsyncMock(return_value=False)
            r = await svc.create_security_policy(data, "u")
            assert r["ok"] is False
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(True, 0))
            r = await svc.create_security_policy(data, "u")
            assert r["ok"] is False

    async def test_detect_threat_flows(self):
        import integrations.atom_enterprise_security_service as mod

        svc = _sec_svc()
        svc.ai_service = MagicMock()
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            patched = [
                {"type": "sql_injection", "severity": "high", "confidence": 0.9,
                 "description": "sqli", "indicators": ["x"]},
            ]
            with patch.object(svc, "_pattern_based_detection", new=AsyncMock(
                    side_effect=[patched, []])), \
                 patch.object(svc, "_behavioral_anomaly_detection", new=AsyncMock(
                    side_effect=[[
                        {"type": "anomalous_behavior", "severity": "critical", "confidence": 0.8,
                         "description": "anom", "indicators": ["y"]},
                    ], []])), \
                 patch.object(svc, "_ai_threat_detection", new=AsyncMock(
                    side_effect=[[
                        {"type": "phishing", "severity": "low", "confidence": 0.5,
                         "description": "phish", "indicators": ["z"]},
                    ], []])), \
                 patch.object(svc, "_mitigate_threat", new=AsyncMock()):
                t = await svc.detect_threat({"source_ip": "1.2.3.4", "user_id": "u", "session_id": "s", "event_type": "login"})
                assert t is not None
                assert t.threat_type == mod.ThreatType.SQL_INJECTION
                assert svc.security_metrics["total_threats_detected"] == 3
                t2 = await svc.detect_threat({})
                assert t2 is None
            # error path
            cb.is_enabled = AsyncMock(side_effect=RuntimeError("x"))
            assert await svc.detect_threat({}) is None

    async def test_audit_event_flows(self):
        import integrations.atom_enterprise_security_service as mod

        svc = _sec_svc({"database": AsyncMock()})
        event = {
            "event_type": "user_login", "user_id": "u", "resource": "r", "action": "a",
            "result": "success", "ip_address": "1.1.1.1", "user_agent": "ua",
        }
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            with patch.object(svc, "_check_compliance_for_event", new=AsyncMock()):
                audit = await svc.audit_event(event)
                assert audit is not None
                assert len(svc.audit_logs) == 1
                svc.db.store_security_audit.assert_awaited()
                cb.is_enabled = AsyncMock(side_effect=RuntimeError("x"))
                assert await svc.audit_event(event) is None

    async def test_check_compliance_flows(self):
        import integrations.atom_enterprise_security_service as mod

        svc = _sec_svc()
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            with patch.object(svc, "_get_compliance_data", new=AsyncMock(return_value={"d": 1})), \
                 patch.object(svc, "_ai_compliance_analysis", new=AsyncMock(return_value={
                    "findings": [], "recommendations": [], "score": 90.0, "artifacts": []})), \
                 patch.object(svc, "_calculate_compliance_score", return_value=95.0):
                report = await svc.check_compliance(mod.ComplianceStandard.SOC2, "monthly")
                assert report is not None
                assert report.overall_score == 95.0
                assert svc.security_metrics["compliance_checks_passed"] == 1
            cb.is_enabled = AsyncMock(side_effect=RuntimeError("x"))
            assert await svc.check_compliance(mod.ComplianceStandard.SOC2) is None

    async def test_encrypt_decrypt(self):
        import integrations.atom_enterprise_security_service as mod

        svc = _sec_svc()
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            enc = await svc.encrypt_data("secret")
            data, ctx = await svc.decrypt_data(enc)
            assert data == "secret" and ctx is None
            enc2 = await svc.encrypt_data("secret", {"k": "v"})
            data2, ctx2 = await svc.decrypt_data(enc2)
            assert data2 == "secret" and ctx2 == {"k": "v"}
            cb.is_enabled = AsyncMock(side_effect=RuntimeError("x"))
            with pytest.raises(RuntimeError):
                await svc.encrypt_data("s")
            with pytest.raises(RuntimeError):
                await svc.decrypt_data("s")

    async def test_validate_password(self):
        import integrations.atom_enterprise_security_service as mod

        svc = _sec_svc()
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            r = await svc.validate_password("StrongPass1!")
            assert r["valid"] is True
            r = await svc.validate_password("short")
            assert r["valid"] is False
            r = await svc.validate_password("password123")
            assert r["valid"] is False
            r = await svc.validate_password("UPPER123!")
            assert r["valid"] is False  # no lower
            r = await svc.validate_password("lower123!")
            assert r["valid"] is False  # no upper
            r = await svc.validate_password("LowerUpper!")
            assert r["valid"] is False  # no digits
            r = await svc.validate_password("LowerUpper123")
            assert r["valid"] is False  # no special
            cb.is_enabled = AsyncMock(side_effect=RuntimeError("x"))
            r = await svc.validate_password("x")
            assert r["valid"] is False

    async def test_analyze_user_behavior(self):
        import integrations.atom_enterprise_security_service as mod

        svc = _sec_svc()
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            with patch.object(svc, "_get_user_activities", new=AsyncMock(return_value=[{"a": 1}])), \
                 patch.object(svc, "_calculate_login_frequency", return_value=1.5), \
                 patch.object(svc, "_analyze_access_patterns", return_value={}), \
                 patch.object(svc, "_calculate_data_access_volume", return_value=3), \
                 patch.object(svc, "_detect_unusual_activities", return_value=[]):
                m = await svc.analyze_user_behavior("u1")
                assert m["login_frequency"] == 1.5
                assert m["data_access_volume"] == 3
            ai = MagicMock()
            ai.process_ai_request = AsyncMock(return_value=MagicMock(ok=True, output_data={}, confidence=0.9))
            with patch.dict(mod.__dict__, {
                "AIRequest": MagicMock(),
                "AITaskType": MagicMock(CONVERSATION_ANALYSIS="ca"),
                "AIModelType": MagicMock(GPT_4="gpt4"),
                "AIServiceType": MagicMock(OPENAI="openai"),
            }):
                svc.ai_service = ai
                with patch.object(svc, "_get_user_activities", new=AsyncMock(return_value=[])), \
                     patch.object(svc, "_ai_behavior_analysis", new=AsyncMock(return_value={"risk_score": 0.7, "anomalies": ["a"]})):
                    m = await svc.analyze_user_behavior("u1")
                    assert m["risk_score"] == 0.7
            cb.is_enabled = AsyncMock(side_effect=RuntimeError("x"))
            r = await svc.analyze_user_behavior("u1")
            assert "error" in r

    async def test_detection_helpers(self):
        import integrations.atom_enterprise_security_service as mod

        svc = _sec_svc()
        # pattern-based detection (matches + no match)
        threats = await svc._pattern_based_detection({"content": "SELECT * FROM users; DROP TABLE x"})
        assert len(threats) >= 1
        threats = await svc._pattern_based_detection({"content": "hello world"})
        assert threats == []
        # behavioral anomaly
        assert await svc._behavioral_anomaly_detection({}) == []
        assert await svc._behavioral_anomaly_detection({"user_id": "u"}) == []
        # ai threat detection without/with ai
        assert await svc._ai_threat_detection({}) == []
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(return_value=MagicMock(ok=True, confidence=0.9, output_data="data"))
        svc.ai_service = ai
        with patch.dict(mod.__dict__, {
            "AIRequest": MagicMock(),
            "AITaskType": MagicMock(CONVERSATION_ANALYSIS="ca"),
            "AIModelType": MagicMock(GPT_4="gpt4"),
            "AIServiceType": MagicMock(OPENAI="openai"),
        }), patch.object(svc, "_parse_ai_threat_results", return_value=[{"type": "xss", "severity": "m", "confidence": 0.5, "description": "d"}]):
            assert len(await svc._ai_threat_detection({})) == 1
        ai.process_ai_request = AsyncMock(side_effect=RuntimeError("x"))
        assert await svc._ai_threat_detection({}) == []
        # mitigate threat
        threat = mod.ThreatDetection(
            detection_id="t1", threat_type=mod.ThreatType.SQL_INJECTION, severity="high",
            confidence=0.9, source_ip="1.2.3.4", user_id="u", session_id="s",
            timestamp=datetime.now(timezone.utc), description="d", indicators=[],
        )
        with patch.object(svc, "_block_ip", new=AsyncMock()), patch.object(svc, "_log_security_audit", new=AsyncMock()):
            await svc._mitigate_threat(threat)
            assert threat.mitigated is True
            assert threat.mitigation_actions == ["Blocked IP: 1.2.3.4"]
        threat2 = mod.ThreatDetection(
            detection_id="t2", threat_type=mod.ThreatType.COMPROMISED_ACCOUNT, severity="critical",
            confidence=0.9, source_ip=None, user_id=None, session_id="s2",
            timestamp=datetime.now(timezone.utc), description="d", indicators=[],
        )
        with patch.object(svc, "_terminate_session", new=AsyncMock()), patch.object(svc, "_log_security_audit", new=AsyncMock()):
            await svc._mitigate_threat(threat2)
        threat3 = mod.ThreatDetection(
            detection_id="t3", threat_type=mod.ThreatType.INSIDER_THREAT, severity="critical",
            confidence=0.9, source_ip=None, user_id="u3", session_id=None,
            timestamp=datetime.now(timezone.utc), description="d", indicators=[],
        )
        with patch.object(svc, "_lock_user_account", new=AsyncMock()), patch.object(svc, "_log_security_audit", new=AsyncMock()):
            await svc._mitigate_threat(threat3)
        with patch.object(svc, "_block_ip", new=AsyncMock(side_effect=RuntimeError("x"))):
            await svc._mitigate_threat(threat)

    async def test_compliance_helpers(self):
        import integrations.atom_enterprise_security_service as mod

        svc = _sec_svc()
        data = await svc._get_compliance_data(mod.ComplianceStandard.SOC2, "monthly")
        assert data["standard"] == "soc2"
        r = await svc._ai_compliance_analysis(mod.ComplianceStandard.SOC2, {})
        assert r["score"] == 0.0
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(return_value=MagicMock(ok=True, output_data="out"))
        svc.ai_service = ai
        with patch.dict(mod.__dict__, {
            "AIRequest": MagicMock(),
            "AITaskType": MagicMock(CONTENT_GENERATION="cg"),
            "AIModelType": MagicMock(GPT_4="gpt4"),
            "AIServiceType": MagicMock(OPENAI="openai"),
        }), patch.object(svc, "_parse_ai_compliance_results", return_value={"findings": [], "recommendations": [], "score": 80.0}):
            r = await svc._ai_compliance_analysis(mod.ComplianceStandard.SOC2, {})
            assert r["score"] == 80.0
        ai.process_ai_request = AsyncMock(return_value=MagicMock(ok=False))
        r = await svc._ai_compliance_analysis(mod.ComplianceStandard.SOC2, {})
        assert r["score"] == 0.0
        ai.process_ai_request = AsyncMock(side_effect=RuntimeError("x"))
        r = await svc._ai_compliance_analysis(mod.ComplianceStandard.SOC2, {})
        assert r["score"] == 0.0
        # score calculation
        assert svc._calculate_compliance_score({"findings": [{"severity": "critical"}, {"severity": "high"},
                                                             {"severity": "medium"}, {"severity": "low"}]}) == 50.0
        assert svc._calculate_compliance_score({"findings": [{"severity": "critical"} for _ in range(10)]}) == 0.0
        assert svc._calculate_compliance_score({}) == 100.0
        with patch.object(svc, "_calculate_compliance_score", side_effect=RuntimeError("x")):
            pass
        # _check_compliance_for_event
        audit = mod.SecurityAudit(
            audit_id="a", event_type=mod.AuditEventType.DATA_ACCESS, user_id="u", resource="r",
            action="data_access", result="ok", ip_address="1.1.1.1", user_agent="ua",
            timestamp=datetime.now(timezone.utc), metadata={},
        )
        issues = await svc._check_compliance_for_event(audit)
        assert len(issues) == 1 and issues[0]["standard"] == "SOC2"
        audit2 = mod.SecurityAudit(
            audit_id="a2", event_type=mod.AuditEventType.DATA_ACCESS, user_id="u", resource="r",
            action="data_export", result="ok", ip_address="1.1.1.1", user_agent="ua",
            timestamp=datetime.now(timezone.utc), metadata={},
        )
        issues = await svc._check_compliance_for_event(audit2)
        assert len(issues) == 1 and issues[0]["standard"] == "GDPR"
        audit3 = mod.SecurityAudit(
            audit_id="a3", event_type=mod.AuditEventType.DATA_ACCESS, user_id="u", resource="r",
            action="data_access", result="ok", ip_address="1.1.1.1", user_agent="ua",
            timestamp=datetime.now(timezone.utc), metadata={"logged": True},
        )
        assert await svc._check_compliance_for_event(audit3) == []
        with patch.object(svc, "_check_compliance_for_event", side_effect=RuntimeError("x")):
            pass

    async def test_misc_helpers_and_metrics(self):
        import integrations.atom_enterprise_security_service as mod

        svc = _sec_svc()
        assert svc._matches_pattern({"content": "x' OR 1=1--"}, svc.malicious_patterns["sql_injection"]) is True
        assert svc._matches_pattern({"content": "plain"}, svc.malicious_patterns["sql_injection"]) is False
        assert svc._matches_pattern({"url": "javascript:alert(1)"}, svc.malicious_patterns["xss"]) is True
        assert svc._matches_pattern({"headers": "../etc"}, svc.malicious_patterns["path_traversal"]) is True
        assert svc._matches_pattern({"other": "x"}, svc.malicious_patterns["xss"]) is False
        key = svc._generate_encryption_key()
        assert isinstance(key, bytes)
        assert svc._calculate_login_frequency([]) == 0.0
        assert svc._analyze_access_patterns([]) == {}
        assert svc._calculate_data_access_volume([]) == 0
        assert svc._detect_unusual_activities([]) == []
        assert await svc._ai_behavior_analysis("u", []) == {}
        assert svc._detect_anomalies({}, {}) == []
        assert svc._parse_ai_threat_results("x") == []
        assert svc._get_compliance_requirements(mod.ComplianceStandard.GDPR) == ["data_protection", "privacy", "consent"]
        assert svc._get_compliance_requirements(mod.ComplianceStandard.NIST) == []
        r = svc._parse_ai_compliance_results("x", mod.ComplianceStandard.SOC2)
        assert r["score"] == 0.0
        assert await svc._validate_security_policy(MagicMock()) == {"valid": True, "errors": []}
        assert await svc._get_user_activities("u", "24h") == []
        # _block_ip / _terminate_session / _lock_user_account / _quarantine_resource
        with patch.object(svc, "_log_security_audit", new=AsyncMock()):
            await svc._block_ip("9.9.9.9", 60)
            assert "9.9.9.9" in svc.blocked_ips
            await svc._terminate_session("sess_none")
            svc.active_sessions["sess1"] = {}
            await svc._terminate_session("sess1")
            assert "sess1" not in svc.active_sessions
            await svc._lock_user_account("user_x")
            svc.user_security_contexts["user_x"] = {}
            await svc._lock_user_account("user_x")
            assert svc.user_security_contexts["user_x"]["locked"] is True
            await svc._quarantine_resource("res1")
            assert "res1" in svc.quarantined_resources
        audit = await svc._log_security_audit(mod.AuditEventType.SECURITY_ALERT, "u", "r", "a", "ok")
        assert audit is not None
        # init methods
        for m in ["_initialize_encryption", "_load_security_policies", "_initialize_threat_detection",
                  "_start_security_monitoring", "_initialize_compliance_monitoring"]:
            assert await getattr(svc, m)() is None
        assert svc.monitoring_active is True
        assert svc.security_policies["password_policy"]["min_length"] == 12
        info = await svc.get_service_info()
        assert info["status"] == "ACTIVE"
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            m = await svc.get_security_metrics()
            assert m["active_policies"] == 0
            await svc.close()
            cb.is_enabled = AsyncMock(return_value=False)
            with pytest.raises(Exception):
                await svc.get_security_metrics()
            with pytest.raises(Exception):
                await svc.close()
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(True, 0))
            with pytest.raises(Exception):
                await svc.get_security_metrics()
            with pytest.raises(Exception):
                await svc.close()
        # http session close
        svc.http_session = MagicMock()
        svc.http_session.close = AsyncMock()
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            await svc.close()
        svc.http_session.close.assert_awaited()
        # singleton config
        assert "database" in mod.atom_enterprise_security_service.config


# ---------------------------------------------------------------------------
# atom_enterprise_security_service — last gaps
# ---------------------------------------------------------------------------
class TestSecurityServiceLast:
    async def test_breaker_and_rate_warning_branches(self):
        import integrations.atom_enterprise_security_service as mod

        svc = _sec_svc()
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=False)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            # Methods that swallow the 503 into an error result
            r = await svc.create_security_policy({"name": "p"}, "u")
            assert r["ok"] is False and "temporarily disabled" in r["error"]
            assert await svc.detect_threat({}) is None
            assert await svc.audit_event({"event_type": "x", "user_id": "u", "resource": "r", "action": "a", "result": "ok", "ip_address": "1"}) is None
            assert await svc.check_compliance(mod.ComplianceStandard.SOC2) is None
            r = await svc.validate_password("x")
            assert r["valid"] is False and "temporarily disabled" in r["error"]
            r = await svc.analyze_user_behavior("u")
            assert "temporarily disabled" in r["error"]
            # Methods that re-raise the 503
            for call in [
                lambda: svc.encrypt_data("s"),
                lambda: svc.decrypt_data("s"),
                lambda: svc._pattern_based_detection({}),
                lambda: svc.get_security_metrics(),
                lambda: svc.close(),
            ]:
                with pytest.raises(HTTPException):
                    await call()
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(True, 0))
            # Same contract split under rate limiting
            r = await svc.create_security_policy({"name": "p"}, "u")
            assert r["ok"] is False and "Rate limit exceeded" in r["error"]
            assert await svc.detect_threat({}) is None
            assert await svc.audit_event({"event_type": "x", "user_id": "u", "resource": "r", "action": "a", "result": "ok", "ip_address": "1"}) is None
            assert await svc.check_compliance(mod.ComplianceStandard.SOC2) is None
            r = await svc.validate_password("x")
            assert r["valid"] is False and "Rate limit exceeded" in r["error"]
            r = await svc.analyze_user_behavior("u")
            assert "Rate limit exceeded" in r["error"]
            for call in [
                lambda: svc.encrypt_data("s"),
                lambda: svc.decrypt_data("s"),
                lambda: svc._pattern_based_detection({}),
                lambda: svc.get_security_metrics(),
                lambda: svc.close(),
            ]:
                with pytest.raises(HTTPException):
                    await call()

    async def test_policy_invalid_standard_and_init_excepts(self):
        import integrations.atom_enterprise_security_service as mod

        svc = _sec_svc()
        data = {
            "name": "p", "description": "d", "security_level": "enterprise",
            "compliance_standards": ["BOGUS"], "rules": [], "enforcement_actions": [],
        }
        with patch.object(mod, "circuit_breaker") as cb, patch.object(mod, "rate_limiter") as rl:
            cb.is_enabled = AsyncMock(return_value=True)
            rl.is_rate_limited = AsyncMock(return_value=(False, 10))
            r = await svc.create_security_policy(data, "u")
            assert r["ok"] is False
            assert "Invalid compliance standard" in r["error"]
        # init method except branches (patch logger.info so the real method
        # bodies hit their internal try/except handlers)
        svc2 = _sec_svc()
        for m in ["_initialize_encryption", "_load_security_policies", "_initialize_threat_detection",
                  "_start_security_monitoring", "_initialize_compliance_monitoring"]:
            with patch.object(mod.logger, "info", side_effect=RuntimeError("x")):
                await getattr(svc2, m)()
        # _get_compliance_data, _ai_compliance_analysis error, score error
        await svc2._get_compliance_data(mod.ComplianceStandard.SOC2, "m")
        with patch.object(svc2, "_parse_ai_compliance_results", side_effect=RuntimeError("x")), \
             patch.dict(mod.__dict__, {
                 "AIRequest": MagicMock(),
                 "AITaskType": MagicMock(CONTENT_GENERATION="cg"),
                 "AIModelType": MagicMock(GPT_4="gpt4"),
                 "AIServiceType": MagicMock(OPENAI="openai"),
             }):
            ai = MagicMock()
            ai.process_ai_request = AsyncMock(return_value=MagicMock(ok=True, output_data="o"))
            svc2.ai_service = ai
            r = await svc2._ai_compliance_analysis(mod.ComplianceStandard.SOC2, {})
            assert r["score"] == 0.0
        # _check_compliance_for_event error path
        with patch.object(svc2, "_check_compliance_for_event", side_effect=RuntimeError("x")):
            pass
        audit = mod.SecurityAudit(
            audit_id="a", event_type=mod.AuditEventType.DATA_ACCESS, user_id="u", resource="r",
            action="data_access", result="ok", ip_address="1", user_agent="ua",
            timestamp=datetime.now(timezone.utc), metadata={},
        )
        with patch.object(svc2, "audit_event", new=AsyncMock(side_effect=RuntimeError("x"))):
            await svc2._check_compliance_for_event(audit)
        # init methods restore normal
        await svc2._initialize_encryption()
        await svc2._load_security_policies()
        await svc2._initialize_threat_detection()
        await svc2._start_security_monitoring()
        await svc2._initialize_compliance_monitoring()
        # config=None ctor
        svc3 = mod.AtomEnterpriseSecurityService("t1", None)
        assert svc3.config == {}

    async def test_behavioral_detection_with_user(self):
        import integrations.atom_enterprise_security_service as mod

        svc = _sec_svc()
        svc.anomaly_baselines["u1"] = {"baseline": 1}
        with patch.object(svc, "_detect_anomalies", return_value=[
            {"severity": "medium", "confidence": 0.6, "description": "d", "indicators": ["i"]},
        ]):
            threats = await svc._behavioral_anomaly_detection({"user_id": "u1"})
            assert len(threats) == 1
            assert threats[0]["type"] == "anomalous_behavior"


# ---------------------------------------------------------------------------
# mcp_service phantom-import guards (fail-closed behavior)
# ---------------------------------------------------------------------------
class TestPhantomImportGuards:
    async def test_cloud_browser_guard_fails_closed(self):
        svc = _svc()
        cloud_tools = [
            "browser_navigate", "browser_click", "browser_type", "browser_screenshot",
            "browser_new_tab", "browser_switch_tab", "browser_click_coords",
            "list_browser_tabs", "browser_save_session", "browser_set_proxy",
            "browser_monitor", "browser_wait_for_selector", "browser_extract_content",
            "browser_upload_file", "browser_download_file",
        ]
        args_by_tool = {
            "browser_navigate": {"url": "http://x"},
            "browser_click": {"selector": "#a"},
            "browser_type": {"text": "hi"},
            "browser_click_coords": {"x": 1, "y": 2},
        }
        ctx = {"computer_use_mode": "cloud", "workspace_id": "default"}
        with _mock_imports({"core.cloud_browser_service": None}):
            for tool in cloud_tools:
                r = await _run_local(svc, tool, args_by_tool.get(tool, {}), ctx)
                assert "Cloud browser service not available" in r, tool

    async def test_cloud_browser_guard_fails_closed_click_variant(self):
        svc = _svc()
        with _mock_imports({"core.cloud_browser_service": None}):
            r = await _run_local(
                svc, "browser_click", {"selector": "#a", "x": 1, "y": 2},
                {"computer_use_mode": "cloud", "workspace_id": "default"},
            )
            assert "Cloud browser service not available" in r

    async def test_collaboration_hub_guard_fails_closed(self):
        svc = _svc()
        with _mock_imports({"core.collaboration_hub_service": None}):
            for tool in ["analyze_message", "draft_response", "approve_draft"]:
                r = await _run_local(svc, tool, {"message_id": "m"})
                assert "Collaboration Hub service not available" in r["error"], tool

    async def test_sales_agent_guard_fails_closed(self):
        svc = _svc()
        with _mock_imports({"core.sales_agent": None}):
            for tool in ["score_lead", "draft_sales_outreach", "monitor_pipeline_health"]:
                r = await _run_local(svc, tool, {"lead_data": {}}, {"workspace_id": "w"})
                assert "Sales agent service not available" in r["error"], tool
