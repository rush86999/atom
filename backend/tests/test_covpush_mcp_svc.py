"""
Coverage push for integrations/mcp_service.py (TESTS ONLY — no source edits).

Raises line coverage of the MCP dispatch hub: registry surface, call_tool
(capability gate, sandbox gate, entity routing, action registry, hardcoded/
dynamic/external servers, not-found), execute_tool branch matrix, HITL policy
checks, integration tool registration/execution, entity context helpers, and
web_search.

Bugs found while reading the module are reported (not fixed).
"""
import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def svc():
    from integrations.mcp_service import MCPService

    s = MCPService()
    s.active_servers = {}
    s.tools_cache = {}
    if hasattr(s, "_permission_cache"):
        s._permission_cache = {}
    return s


def _session_factory(db):
    """Factory for `with SessionLocal() as db:` — returns an async-CM-like mock."""
    cm = MagicMock()
    cm.__enter__.return_value = db
    cm.__exit__.return_value = False
    factory = MagicMock(return_value=cm)
    return factory


def _query_first(value=None, all_value=None):
    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = value
    q.all.return_value = all_value
    return q


def _fake_universal_cls(execute_result=None, search_result=None, execute_raises=None):
    inst = MagicMock()
    if execute_result is not None:
        inst.execute = AsyncMock(return_value=execute_result)
    if search_result is not None:
        inst.search = AsyncMock(return_value=search_result)
    if execute_raises is not None:
        inst.execute = AsyncMock(side_effect=execute_raises)
    cls = MagicMock(return_value=inst)
    return cls, inst


# ============================================================================
# Basic surface: singleton, capabilities, health, connections
# ============================================================================


class TestSurface:
    def test_singleton(self):
        from integrations.mcp_service import MCPService

        a = MCPService()
        b = MCPService()
        assert a is b
        assert hasattr(a, "initialized")

    def test_get_capabilities(self, svc):
        caps = svc.get_capabilities()
        assert caps["supports_webhooks"] is False
        assert len(caps["operations"]) == 5

    def test_health_check_healthy(self, svc):
        result = svc.health_check()
        assert result["ok"] is True
        assert result["status"] == "healthy"

    def test_health_check_uninitialized(self):
        from integrations.mcp_service import MCPService

        s = MCPService()
        s.initialized = False
        result = s.health_check()
        assert result["ok"] is False
        assert result["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_get_active_connections(self, svc):
        svc.active_servers = {
            "svc1": {"name": "Server One", "connected_at": "now"},
            "svc2": {"name": None},
        }
        conns = await svc.get_active_connections()
        assert conns[0]["server_id"] == "svc1"
        assert conns[0]["status"] == "connected"
        assert conns[1]["name"] is None

    @pytest.mark.asyncio
    async def test_get_server_tools_google_search(self, svc):
        tools = await svc.get_server_tools("google-search")
        names = [t["name"] for t in tools]
        assert "web_search" in names and "fetch_page" in names

    @pytest.mark.asyncio
    async def test_get_server_tools_local_tools(self, svc):
        tools = await svc.get_server_tools("local-tools")
        names = [t["name"] for t in tools]
        for expected in [
            "discover_connections",
            "search_contacts",
            "create_crm_lead",
            "get_sales_pipeline",
            "update_crm_lead",
            "create_crm_deal",
            "update_crm_deal",
            "list_projects",
            "get_tasks",
            "create_task",
            "update_task",
            "create_support_ticket",
            "update_support_ticket",
            "ingest_knowledge_from_text",
            "ingest_knowledge_from_file",
            "query_knowledge_graph",
            "save_business_fact",
            "verify_citation",
            "search_tasks",
            "search_formulas",
            "canvas_tool",
            "analyze_message",
            "draft_response",
            "approve_draft",
            "send_message",
            "ingest_message_attachment",
            "post_channel_message",
            "send_email",
            "search_emails",
            "unified_communication_search",
            "whatsapp_send_message",
            "whatsapp_send_template",
            "whatsapp_list_templates",
            "search_files",
            "upload_file_to_storage",
            "create_storage_folder",
            "list_files",
            "unified_knowledge_search",
            "manage_reviews",
            "request_testimonial",
            "analyze_ads_performance",
            "score_lead",
            "draft_sales_outreach",
            "monitor_pipeline_health",
            "b2b_extract_po",
            "b2b_create_draft_order",
            "b2b_push_to_integrations",
            "shopify_create_product",
            "shopify_update_inventory",
            "shopify_get_orders",
            "query_financial_metrics",
            "list_finance_invoices",
            "finance_close_check",
            "create_invoice",
            "push_to_integration",
            "create_ecommerce_order",
            "add_marketing_subscriber",
            "create_record",
            "update_record",
            "list_agents",
            "spawn_agent",
            "list_workflows",
            "trigger_workflow",
            "get_system_health",
            "request_human_intervention",
            "generate_pdf_report",
            "create_shipment",
            "get_shipping_rates",
            "create_shipping_label",
            "track_shipment",
            "validate_address",
            "s3_upload",
            "s3_download",
            "lambda_invoke",
            "sqs_send",
            "sns_publish",
            "azure_blob_upload",
            "azure_blob_download",
            "azure_function_invoke",
            "gcs_upload",
            "gcs_download",
            "cloud_function_invoke",
            "pubsub_publish",
            "call_integration",
            "list_integrations",
            "browser_navigate",
            "browser_click",
            "browser_type",
            "browser_screenshot",
        ]:
            assert expected in names, f"local-tools missing {expected}"

    @pytest.mark.asyncio
    async def test_get_server_tools_unknown_server(self, svc):
        svc.active_servers = {"other": {"tools": [{"name": "t"}]}}
        assert await svc.get_server_tools("other") == [{"name": "t"}]
        assert await svc.get_server_tools("missing") == []

    @pytest.mark.asyncio
    async def test_get_openai_tools(self, svc, monkeypatch):
        monkeypatch.setattr(
            svc, "get_all_tools", AsyncMock(return_value=[{"name": "t1"}])
        )
        monkeypatch.setattr(
            "integrations.mcp_service.MCPToolConverter.convert_to_openai_tools",
            staticmethod(lambda tools: [{"type": "function", "name": tools[0]["name"]}]),
        )
        result = await svc.get_openai_tools()
        assert result[0]["name"] == "t1"

    @pytest.mark.asyncio
    async def test_get_all_tools(self, svc, monkeypatch):
        from core.action_registry import action_registry

        fake_registry = MagicMock()
        fake_registry.get_simplified_tools.return_value = [
            {"name": "registry_tool", "description": "d"}
        ]
        monkeypatch.setattr("integrations.mcp_service.get_tool_registry", lambda: fake_registry)
        monkeypatch.setattr(
            "core.action_registry.action_registry.get_all_definitions",
            lambda: [
                SimpleNamespace(
                    name="covpush.action",
                    description="d",
                    parameters_schema={
                        "properties": {"q": {"type": "string"}},
                        "required": ["q"],
                    },
                )
            ],
        )
        svc.active_servers = {
            "ext-srv": {"tools": [{"name": "ext_tool", "description": "x"}]}
        }
        all_tools = await svc.get_all_tools()
        names = {t["name"] for t in all_tools}
        assert "registry_tool" in names
        assert "covpush.action" in names
        assert "ext_tool" in names
        assert "global_search" in names
        action_tool = next(t for t in all_tools if t["name"] == "covpush.action")
        assert action_tool["parameters"]["q"] == "string"


# ============================================================================
# execute_operation
# ============================================================================


class TestExecuteOperation:
    @pytest.mark.asyncio
    async def test_operation_dispatch(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "get_openai_tools", AsyncMock(return_value=[1]))
        monkeypatch.setattr(svc, "get_server_tools", AsyncMock(return_value=[2]))
        monkeypatch.setattr(svc, "call_tool", AsyncMock(return_value={"r": 1}))
        monkeypatch.setattr(svc, "search_tools", AsyncMock(return_value=[3]))
        monkeypatch.setattr(svc, "web_search", AsyncMock(return_value={"q": "x"}))

        assert (await svc.execute_operation("get_openai_tools", {}))["success"] is True
        res = await svc.execute_operation("get_server_tools", {"server_id": "s"})
        assert res["result"] == [2]
        res = await svc.execute_operation("call_tool", {"tool_name": "t", "arguments": {"a": 1}}, {"tenant_id": "t1"})
        assert res["result"] == {"r": 1}
        res = await svc.execute_operation("search_tools", {"query": "q", "limit": 2})
        assert res["result"] == [3]
        res = await svc.execute_operation("web_search", {"query": "q"}, {"tenant_id": "t1"})
        assert res["result"] == {"q": "x"}
        res = await svc.execute_operation("nope", {})
        assert res["success"] is False and "Unknown operation" in res["error"]

    @pytest.mark.asyncio
    async def test_operation_exception(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "web_search", AsyncMock(side_effect=RuntimeError("boom")))
        res = await svc.execute_operation("web_search", {"query": "q"}, {"tenant_id": "t"})
        assert res["success"] is False
        assert "boom" in res["error"]

    @pytest.mark.asyncio
    async def test_operation_missing_params_uses_defaults(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "search_tools", AsyncMock(return_value=[]))
        res = await svc.execute_operation("search_tools", {})
        assert res["success"] is True


# ============================================================================
# call_tool: gates + resolution branches
# ============================================================================


class TestCallToolGates:
    @pytest.mark.asyncio
    async def test_capability_gate_blocks(self, svc, monkeypatch):
        agent = MagicMock()
        agent.capabilities = ["allowed_tool"]
        monkeypatch.setattr(
            "core.capability_resolver.get_agent_for_context", lambda ctx: agent
        )
        result = await svc.call_tool(
            "forbidden_tool", {}, {"agent_id": "a1", "tier": "student"}
        )
        assert result["blocked_by"] == "capability_gate"

    @pytest.mark.asyncio
    async def test_capability_gate_tier_at_issuance(self, svc, monkeypatch):
        agent = MagicMock()
        agent.capabilities = ["allowed_tool"]
        monkeypatch.setattr(
            "core.capability_resolver.get_agent_for_context", lambda ctx: agent
        )
        result = await svc.call_tool(
            "forbidden_tool", {}, {"agent_id": "a1", "tier_at_issuance": "student"}
        )
        assert result["blocked_by"] == "capability_gate"

    @pytest.mark.asyncio
    async def test_capability_gate_fail_open(self, svc, monkeypatch):
        monkeypatch.setattr(
            "core.capability_resolver.get_agent_for_context",
            lambda ctx: (_ for _ in ()).throw(RuntimeError("db down")),
        )
        result = await svc.call_tool("no_such_tool_xyz", {})
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_sandbox_enforced_block(self, svc, monkeypatch):
        decision = MagicMock()
        decision.requires_review = True
        decision.enforced = True
        decision.decision = "blocked"
        decision.violation_detail = "no egress"
        monkeypatch.setattr(
            "core.sandbox_gate.evaluate_tool_call", lambda *a, **k: decision
        )
        result = await svc.call_tool("anything", {}, {"agent_id": "a1"})
        assert "blocked" in result

    @pytest.mark.asyncio
    async def test_sandbox_shadow_mode_proceeds(self, svc, monkeypatch):
        decision = MagicMock()
        decision.requires_review = True
        decision.enforced = False
        decision.violation_type = "vt"
        monkeypatch.setattr(
            "core.sandbox_gate.evaluate_tool_call", lambda *a, **k: decision
        )
        monkeypatch.setattr(svc, "execute_tool", AsyncMock(return_value="ran"))
        monkeypatch.setattr(
            "core.action_registry.action_registry.get_action", lambda n: None
        )
        monkeypatch.setattr(
            "core.action_registry.action_registry.execute_action",
            AsyncMock(side_effect=KeyError("unused")),
        )
        result = await svc.call_tool("web_search", {}, {})
        assert result == "ran"

    @pytest.mark.asyncio
    async def test_sandbox_gate_raises_fail_open(self, svc, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("sandbox broken")

        monkeypatch.setattr("core.sandbox_gate.evaluate_tool_call", boom)
        monkeypatch.setattr(
            "core.action_registry.action_registry.get_action", lambda n: None
        )
        monkeypatch.setattr(
            "core.action_registry.action_registry.execute_action",
            AsyncMock(side_effect=KeyError("unused")),
        )
        monkeypatch.setattr(svc, "execute_tool", AsyncMock(return_value="ok"))
        assert await svc.call_tool("web_search", {}, {}) == "ok"


class TestCallToolResolution:
    @pytest.mark.asyncio
    async def test_entity_bound_routing(self, svc, monkeypatch):
        monkeypatch.setattr(
            svc, "execute_entity_tool", AsyncMock(return_value={"status": "success"})
        )
        result = await svc.call_tool(
            "some_tool",
            {},
            {"entity_id": "e1", "entity_type_slug": "vendor", "tenant_id": "t"},
        )
        assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_action_registry_execution(self, svc, monkeypatch):
        handler = AsyncMock(return_value={"action": "done"})
        action = SimpleNamespace(name="covpush.act", handler=handler)
        monkeypatch.setattr(
            "core.action_registry.action_registry.get_action",
            lambda n: action if n == "covpush.act" else None,
        )
        monkeypatch.setattr(
            "core.action_registry.action_registry.execute_action",
            AsyncMock(return_value={"action": "done"}),
        )
        result = await svc.call_tool("covpush.act", {"x": 1}, {"user_id": "u"})
        assert result == {"action": "done"}

    @pytest.mark.asyncio
    async def test_hardcoded_server_dispatch(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "execute_tool", AsyncMock(return_value="executed"))
        result = await svc.call_tool("fetch_page", {"url": "http://x"})
        assert result == "executed"
        result = await svc.call_tool("web_search", {"query": "q"})
        assert result == "executed"

    @pytest.mark.asyncio
    async def test_dynamic_server_dispatch(self, svc, monkeypatch):
        svc.active_servers = {"dyn": {"tools": [{"name": "dyn_tool"}]}}
        executed = AsyncMock(return_value="ok")
        monkeypatch.setattr(svc, "execute_tool", executed)
        result = await svc.call_tool("dyn_tool", {"a": 1}, {"tenant_id": "t"})
        assert result == "ok"
        assert executed.await_args.args[0] == "dyn"

    @pytest.mark.asyncio
    async def test_external_hub_dispatch(self, svc, monkeypatch):
        hub = MagicMock()
        hub.tools_cache = {"ext-svc": [SimpleNamespace(name="ext_tool")]}
        hub.call_external_tool = AsyncMock(return_value="external")
        monkeypatch.setattr("core.mcp_service.mcp_service", hub)
        result = await svc.call_tool("ext_tool", {"q": 1})
        assert result == "external"

    @pytest.mark.asyncio
    async def test_external_hub_skips_hardcoded_servers(self, svc, monkeypatch):
        hub = MagicMock()
        hub.tools_cache = {"google-search": [SimpleNamespace(name="web_search")]}
        hub.call_external_tool = AsyncMock(return_value="external")
        monkeypatch.setattr("core.mcp_service.mcp_service", hub)
        monkeypatch.setattr(svc, "execute_tool", AsyncMock(return_value="local"))
        assert await svc.call_tool("web_search", {}) == "local"

    @pytest.mark.asyncio
    async def test_external_hub_error_falls_through(self, svc, monkeypatch):
        hub = MagicMock()
        hub.tools_cache = {"ext-svc": [SimpleNamespace(name="ext_tool")]}
        hub.call_external_tool = AsyncMock(side_effect=RuntimeError("hub down"))
        monkeypatch.setattr("core.mcp_service.mcp_service", hub)
        result = await svc.call_tool("ext_tool", {})
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_tool_not_found(self, svc, monkeypatch):
        monkeypatch.setattr(
            "core.action_registry.action_registry.get_action", lambda n: None
        )
        monkeypatch.setattr(
            "core.action_registry.action_registry.execute_action",
            AsyncMock(side_effect=KeyError("unused")),
        )
        result = await svc.call_tool("ghost_tool", {}, {})
        assert "not found" in result["error"]


# ============================================================================
# search_tools
# ============================================================================


class TestSearchTools:
    @pytest.mark.asyncio
    async def test_search_tools_match_sort_limit(self, svc, monkeypatch):
        monkeypatch.setattr(
            svc,
            "get_all_tools",
            AsyncMock(
                return_value=[
                    {"name": "alpha_tool", "description": "alpha stuff"},
                    {"name": "beta_tool", "description": "ALPHA related"},
                    {"name": "gamma", "description": "nothing"},
                ]
            ),
        )
        matches = await svc.search_tools("alpha")
        assert [m["name"] for m in matches] == ["alpha_tool", "beta_tool"]
        assert len(await svc.search_tools("alpha", limit=1)) == 1


# ============================================================================
# register_integration_tools
# ============================================================================


class TestRegisterIntegrationTools:
    def _integrations(self):
        i1 = MagicMock()
        i1.connector_id = "salesforce"
        i2 = MagicMock()
        i2.connector_id = "noservice"
        i3 = MagicMock()
        i3.connector_id = "noops"
        return [i1, i2, i3]

    @pytest.mark.asyncio
    async def test_register_with_db(self, svc, monkeypatch):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = self._integrations()

        svc1 = MagicMock()
        svc1.get_operations.return_value = [
            {"name": "op1", "description": "d1", "parameters": {"p": "x"}, "complexity": 3},
            {"name": "op2"},
        ]
        svc3 = MagicMock(spec=[])

        def _get_service(connector_id, tenant_id):
            if connector_id == "salesforce":
                return svc1
            if connector_id == "noservice":
                return None
            if connector_id == "noops":
                return svc3
            return MagicMock()

        fake_registry_cls = MagicMock()
        fake_registry = fake_registry_cls.return_value
        fake_registry.get_service_instance = AsyncMock(side_effect=_get_service)
        monkeypatch.setattr("core.integration_registry.IntegrationRegistry", fake_registry_cls)

        registered = await svc.register_integration_tools("tenant-1", db=db)
        assert len(registered) == 2
        assert registered[0]["name"] == "salesforce_op1"
        assert registered[0]["server_id"] == "integration"
        assert registered[0]["complexity"] == 3
        assert "tenant-1:salesforce:op1" in svc.tools_cache
        db.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_creates_tools_cache_if_absent(self, svc, monkeypatch):
        del svc.tools_cache
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = self._integrations()
        svc1 = MagicMock()
        svc1.get_operations.return_value = [{"name": "op1"}]
        fake_registry_cls = MagicMock()
        fake_registry = fake_registry_cls.return_value
        fake_registry.get_service_instance = AsyncMock(
            side_effect=lambda connector_id, tenant_id: svc1 if connector_id == "salesforce" else None
        )
        monkeypatch.setattr("core.integration_registry.IntegrationRegistry", fake_registry_cls)
        registered = await svc.register_integration_tools("tenant-1", db=db)
        assert len(registered) == 1
        assert hasattr(svc, "tools_cache")

    @pytest.mark.asyncio
    async def test_register_connector_exception_continues(self, svc, monkeypatch):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = self._integrations()

        def _get_service(connector_id, tenant_id):
            raise RuntimeError("service broken")

        fake_registry_cls = MagicMock()
        fake_registry = fake_registry_cls.return_value
        fake_registry.get_service_instance = AsyncMock(side_effect=_get_service)
        monkeypatch.setattr("core.integration_registry.IntegrationRegistry", fake_registry_cls)

        registered = await svc.register_integration_tools("tenant-1", db=db)
        assert registered == []

    @pytest.mark.asyncio
    async def test_register_creates_and_closes_session(self, svc, monkeypatch):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        monkeypatch.setattr("integrations.mcp_service.SessionLocal", lambda: db)
        fake_registry_cls = MagicMock()
        fake_registry_cls.return_value.get_service_instance = AsyncMock(return_value=None)
        monkeypatch.setattr("core.integration_registry.IntegrationRegistry", fake_registry_cls)
        registered = await svc.register_integration_tools("tenant-1")
        assert registered == []
        db.close.assert_called_once()


# ============================================================================
# execute_integration_tool
# ============================================================================


class TestExecuteIntegrationTool:
    @pytest.mark.asyncio
    async def test_bad_tool_name_format(self, svc):
        result = await svc.execute_integration_tool("plain", {}, {"tenant_id": "t"})
        assert result["status"] == "error"
        assert "Invalid tool name format" in result["error"]

    @pytest.mark.asyncio
    async def test_missing_context_fields(self, svc):
        result = await svc.execute_integration_tool("svc_op", {}, {"tenant_id": "t"})
        assert result["status"] == "error"
        assert "tenant_id and agent_id" in result["error"]

    @pytest.mark.asyncio
    async def test_success_delegates_to_universal(self, svc, monkeypatch):
        cls, inst = _fake_universal_cls(execute_result={"status": "success", "data": {}})
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_integration_tool(
            "hubspot_create",
            {"email": "x@y.z"},
            {"tenant_id": "t", "agent_id": "a", "workspace_id": "w", "user_id": "u"},
        )
        assert result["status"] == "success"
        inst.execute.assert_awaited_once()
        assert inst.execute.await_args.args[0] == "hubspot"

    @pytest.mark.asyncio
    async def test_execution_error(self, svc, monkeypatch):
        cls, inst = _fake_universal_cls(execute_raises=RuntimeError("failed"))
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_integration_tool(
            "hubspot_create", {}, {"tenant_id": "t", "agent_id": "a"}
        )
        assert result["status"] == "error"
        assert "failed" in result["error"]


# ============================================================================
# execute_tool: registry path
# ============================================================================


class TestExecuteToolRegistry:
    @pytest.mark.asyncio
    async def test_async_registry_function(self, svc, monkeypatch):
        async def _fn(x=1):
            return x * 2

        fake_registry = MagicMock()
        fake_registry.get.return_value = MagicMock()
        fake_registry.get_function.return_value = _fn
        monkeypatch.setattr("integrations.mcp_service.get_tool_registry", lambda: fake_registry)

        result = await svc.execute_tool(
            "local-tools", "covpush_async", {"x": 21}, {"agent_id": "a"}
        )
        assert result == 42

    @pytest.mark.asyncio
    async def test_sync_registry_function_context_keys_filtered(self, svc, monkeypatch):
        def _fn(x=1, **extra):
            return x

        fake_registry = MagicMock()
        fake_registry.get.return_value = MagicMock()
        fake_registry.get_function.return_value = _fn
        monkeypatch.setattr("integrations.mcp_service.get_tool_registry", lambda: fake_registry)

        result = await svc.execute_tool(
            "local-tools", "covpush_sync", {"x": 7}, {"agent_id": "a", "tenant_id": "t"}
        )
        assert result == 7

    @pytest.mark.asyncio
    async def test_signature_inspection_failure_is_tolerated(self, svc, monkeypatch):
        def _fn(x=1, **extra):
            return x

        fake_registry = MagicMock()
        fake_registry.get.return_value = MagicMock()
        fake_registry.get_function.return_value = _fn
        monkeypatch.setattr("integrations.mcp_service.get_tool_registry", lambda: fake_registry)
        monkeypatch.setattr(
            "integrations.mcp_service.inspect.signature",
            lambda fn: (_ for _ in ()).throw(ValueError("no sig")),
        )
        result = await svc.execute_tool(
            "google-search", "covpush_sig", {"x": 3}, {"agent_id": "a"}
        )
        assert result == 3

    @pytest.mark.asyncio
    async def test_registry_metadata_but_no_function_raises(self, svc, monkeypatch):
        fake_registry = MagicMock()
        fake_registry.get.return_value = MagicMock()
        fake_registry.get_function.return_value = None
        monkeypatch.setattr("integrations.mcp_service.get_tool_registry", lambda: fake_registry)
        with pytest.raises(ValueError):
            await svc.execute_tool("local-tools", "covpush_none", {}, {})


def _no_registry(monkeypatch):
    reg = MagicMock()
    reg.get.return_value = None
    monkeypatch.setattr("integrations.mcp_service.get_tool_registry", lambda: reg)


def _fake_module(monkeypatch, name, **attrs):
    import types

    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    monkeypatch.setitem(sys.modules, name, mod)
    return mod


# ============================================================================
# execute_tool: local-tools branch matrix
# ============================================================================


class TestExecuteToolLocalTools:
    @pytest.fixture(autouse=True)
    def _neutralize_registry(self, monkeypatch):
        _no_registry(monkeypatch)

    @pytest.mark.asyncio
    async def test_finance_close_check(self, svc, monkeypatch):
        agent = MagicMock()
        agent.run_close_check = AsyncMock(return_value={"ok": True})
        monkeypatch.setattr(
            "accounting.close_agent.CloseChecklistAgent", lambda db: agent
        )
        monkeypatch.setattr(
            "core.database.SessionLocal", _session_factory(MagicMock())
        )
        result = await svc.execute_tool(
            "local-tools", "finance_close_check", {}, {"workspace_id": "default"}
        )
        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_b2b_extract_po(self, svc, monkeypatch):
        service = MagicMock()
        service.extract_po_from_text = AsyncMock(return_value={"po": 1})
        _fake_module(
            monkeypatch,
            "ecommerce.b2b_procurement_service",
            B2BProcurementService=lambda db: service,
        )
        monkeypatch.setattr(
            "core.database.SessionLocal", _session_factory(MagicMock())
        )
        result = await svc.execute_tool(
            "local-tools", "b2b_extract_po", {"text": "hello"}, {}
        )
        assert result == {"po": 1}

    @pytest.mark.asyncio
    async def test_b2b_create_draft_order(self, svc, monkeypatch):
        service = MagicMock()
        service.create_draft_order_from_po = AsyncMock(return_value="draft-1")
        _fake_module(
            monkeypatch,
            "ecommerce.b2b_procurement_service",
            B2BProcurementService=lambda db: service,
        )
        monkeypatch.setattr(
            "core.database.SessionLocal", _session_factory(MagicMock())
        )
        result = await svc.execute_tool(
            "local-tools",
            "b2b_create_draft_order",
            {"workspace_id": "w1", "customer_email": "c@x", "po_data": {}},
            {},
        )
        assert result == "draft-1"

    @pytest.mark.asyncio
    async def test_b2b_push_to_integrations(self, svc, monkeypatch):
        service = MagicMock()
        service.push_draft_order = AsyncMock(return_value={"pushed": True})
        _fake_module(
            monkeypatch,
            "ecommerce.b2b_data_push_service",
            B2BDataPushService=lambda db: service,
        )
        monkeypatch.setattr(
            "core.database.SessionLocal", _session_factory(MagicMock())
        )
        result = await svc.execute_tool(
            "local-tools", "b2b_push_to_integrations", {"order_id": "o1"}, {}
        )
        assert result == {"pushed": True}

    @pytest.mark.asyncio
    async def test_request_human_intervention(self, svc, monkeypatch):
        intervention = MagicMock()
        intervention.request_intervention = AsyncMock(return_value={"approved": True})
        monkeypatch.setattr("core.intervention_service.intervention_service", intervention)
        result = await svc.execute_tool(
            "local-tools",
            "request_human_intervention",
            {"action": "refund", "reason": "customer", "params": {"amt": 10}},
            {"workspace_id": "ws", "tenant_id": "t"},
        )
        assert result == {"approved": True}

    @pytest.mark.asyncio
    async def test_trigger_workflow_missing_id(self, svc):
        result = await svc.execute_tool("local-tools", "trigger_workflow", {}, {})
        assert result == {"error": "workflow_id is required"}

    @pytest.mark.asyncio
    async def test_trigger_workflow_refused_critical(self, svc, monkeypatch):
        orchestrator = MagicMock()
        monkeypatch.setattr(
            "advanced_workflow_orchestrator.get_orchestrator", lambda: orchestrator
        )
        monkeypatch.setattr(
            "core.workflow_security.resolve_orchestrator_steps", lambda o, w: [{"critical": True}]
        )
        monkeypatch.setattr("core.workflow_security.has_critical_step", lambda s: True)
        result = await svc.execute_tool(
            "local-tools", "trigger_workflow", {"workflow_id": "wf"}, {}
        )
        assert "refused" in result["error"]

    @pytest.mark.asyncio
    async def test_trigger_workflow_success(self, svc, monkeypatch):
        orchestrator = MagicMock()
        ctx = SimpleNamespace(
            status=SimpleNamespace(value="completed"),
            workflow_id="wf1",
            results={"r": 1},
            error_message=None,
        )
        orchestrator.execute_workflow = AsyncMock(return_value=ctx)
        monkeypatch.setattr(
            "advanced_workflow_orchestrator.get_orchestrator", lambda: orchestrator
        )
        monkeypatch.setattr(
            "core.workflow_security.resolve_orchestrator_steps", lambda o, w: []
        )
        monkeypatch.setattr("core.workflow_security.has_critical_step", lambda s: False)
        result = await svc.execute_tool(
            "local-tools",
            "trigger_workflow",
            {"workflow_id": "wf", "input_data": {"x": 1}},
            {},
        )
        assert result["status"] == "completed"
        assert result["execution_id"] == "wf1"

    @pytest.mark.asyncio
    async def test_marketing_review_request(self, svc, monkeypatch):
        agent = MagicMock()
        agent.trigger_review_request = AsyncMock(return_value="reviewed")
        monkeypatch.setattr(
            "core.marketing_agent.MarketingAgent", lambda db_session=None: agent
        )
        monkeypatch.setattr(
            "core.database.SessionLocal", _session_factory(MagicMock())
        )
        result = await svc.execute_tool(
            "local-tools", "marketing_review_request", {"customer_id": "c1"}, {}
        )
        assert result == "reviewed"

    @pytest.mark.asyncio
    async def test_track_competitor_pricing(self, svc, monkeypatch):
        agent = MagicMock()
        agent.track_competitor_pricing = AsyncMock(return_value="prices")
        monkeypatch.setattr(
            "operations.automations.competitive_intel.CompetitiveIntelWorkflow",
            lambda: agent,
        )
        result = await svc.execute_tool(
            "local-tools",
            "track_competitor_pricing",
            {"competitors": ["A"], "product": "widget"},
            {},
        )
        assert result == "prices"

    @pytest.mark.asyncio
    async def test_reconcile_inventory(self, svc, monkeypatch):
        agent = MagicMock()
        agent.reconcile_inventory = AsyncMock(return_value="reconciled")
        monkeypatch.setattr(
            "operations.automations.inventory_reconcile.InventoryReconciliationWorkflow",
            lambda: agent,
        )
        result = await svc.execute_tool(
            "local-tools", "reconcile_inventory", {}, {}
        )
        assert result == "reconciled"

    @pytest.mark.asyncio
    async def test_canvas_tool(self, svc, monkeypatch):
        manager = MagicMock()
        manager.broadcast_event = AsyncMock(return_value=None)
        monkeypatch.setattr("core.websockets.get_connection_manager", lambda: manager)
        result = await svc.execute_tool(
            "local-tools",
            "canvas_tool",
            {"action": "present", "component": "chart", "data": {"x": 1}, "title": "T"},
            {"workspace_id": "ws", "agent_id": "a1"},
        )
        assert "sent" in result
        manager.broadcast_event.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_communication_hub_tools_import_error(self, svc, monkeypatch):
        monkeypatch.setitem(sys.modules, "core.collaboration_hub_service", None)
        for tool in ["analyze_message", "draft_response", "approve_draft"]:
            result = await svc.execute_tool("local-tools", tool, {"message_id": "m"}, {})
            assert "Collaboration Hub service not available" in result["error"]

    @pytest.mark.asyncio
    async def test_ingest_message_attachment(self, svc):
        result = await svc.execute_tool(
            "local-tools", "ingest_message_attachment", {"file_name": "f.txt"}, {}
        )
        assert "ingested" in result

    @pytest.mark.asyncio
    async def test_shopify_no_store(self, svc, monkeypatch):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        monkeypatch.setattr(
            "core.database.SessionLocal", _session_factory(db)
        )
        result = await svc.execute_tool(
            "local-tools", "shopify_create_product", {"title": "p"}, {"workspace_id": "ws"}
        )
        assert result == "No Shopify store connected to this workspace."

    @pytest.mark.asyncio
    async def test_shopify_create_product_created(self, svc, monkeypatch):
        db = MagicMock()
        store = MagicMock()
        store.access_token = "tok"
        store.shop_domain = "shop.myshopify.com"
        db.query.return_value.filter.return_value.first.return_value = store
        monkeypatch.setattr(
            "core.database.SessionLocal", _session_factory(db)
        )

        service = MagicMock()
        service._get_base_url = lambda shop: f"https://{shop}/admin"
        service._get_headers = lambda token: {"X": token}
        service.get_orders = AsyncMock(return_value=[])
        monkeypatch.setattr(
            "integrations.shopify_service.ShopifyService", lambda: service
        )

        resp = MagicMock()
        resp.status_code = 201
        resp.json.return_value = {"product": {"id": "123"}}
        client = MagicMock()
        client.post = AsyncMock(return_value=resp)
        client.get = AsyncMock(return_value=resp)
        http_cls = MagicMock()
        http_cls.return_value.__aenter__ = AsyncMock(return_value=client)
        http_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr("integrations.mcp_service.httpx.AsyncClient", http_cls)

        result = await svc.execute_tool(
            "local-tools",
            "shopify_create_product",
            {"title": "p"},
            {"workspace_id": "ws"},
        )
        assert "Product created successfully: 123" in result

    @pytest.mark.asyncio
    async def test_shopify_create_product_failed(self, svc, monkeypatch):
        db = MagicMock()
        store = MagicMock()
        store.access_token = "tok"
        store.shop_domain = "shop.myshopify.com"
        db.query.return_value.filter.return_value.first.return_value = store
        monkeypatch.setattr(
            "core.database.SessionLocal", _session_factory(db)
        )
        service = MagicMock()
        service._get_base_url = lambda shop: "u"
        service._get_headers = lambda token: {}
        monkeypatch.setattr(
            "integrations.shopify_service.ShopifyService", lambda: service
        )
        resp = MagicMock()
        resp.status_code = 400
        resp.text = "bad"
        client = MagicMock()
        client.post = AsyncMock(return_value=resp)
        http_cls = MagicMock()
        http_cls.return_value.__aenter__ = AsyncMock(return_value=client)
        http_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr("integrations.mcp_service.httpx.AsyncClient", http_cls)
        result = await svc.execute_tool(
            "local-tools", "shopify_create_product", {}, {"workspace_id": "ws"}
        )
        assert "Failed to create product: bad" in result

    @pytest.mark.asyncio
    async def test_shopify_update_inventory(self, svc, monkeypatch):
        db = MagicMock()
        store = MagicMock()
        store.access_token = "tok"
        store.shop_domain = "shop"
        db.query.return_value.filter.return_value.first.return_value = store
        monkeypatch.setattr(
            "core.database.SessionLocal", _session_factory(db)
        )
        service = MagicMock()
        service._get_base_url = lambda shop: "u"
        service._get_headers = lambda token: {}
        monkeypatch.setattr(
            "integrations.shopify_service.ShopifyService", lambda: service
        )
        resp = MagicMock()
        resp.status_code = 200
        client = MagicMock()
        client.post = AsyncMock(return_value=resp)
        http_cls = MagicMock()
        http_cls.return_value.__aenter__ = AsyncMock(return_value=client)
        http_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr("integrations.mcp_service.httpx.AsyncClient", http_cls)
        result = await svc.execute_tool(
            "local-tools",
            "shopify_update_inventory",
            {"inventory_item_id": "i", "location_id": "l", "available": 5},
            {"workspace_id": "ws"},
        )
        assert "Inventory updated successfully." == result

    @pytest.mark.asyncio
    async def test_shopify_update_inventory_failed(self, svc, monkeypatch):
        db = MagicMock()
        store = MagicMock()
        store.access_token = "tok"
        store.shop_domain = "shop"
        db.query.return_value.filter.return_value.first.return_value = store
        monkeypatch.setattr(
            "core.database.SessionLocal", _session_factory(db)
        )
        service = MagicMock()
        service._get_base_url = lambda shop: "u"
        service._get_headers = lambda token: {}
        monkeypatch.setattr(
            "integrations.shopify_service.ShopifyService", lambda: service
        )
        resp = MagicMock()
        resp.status_code = 500
        resp.text = "nope"
        client = MagicMock()
        client.post = AsyncMock(return_value=resp)
        http_cls = MagicMock()
        http_cls.return_value.__aenter__ = AsyncMock(return_value=client)
        http_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr("integrations.mcp_service.httpx.AsyncClient", http_cls)
        result = await svc.execute_tool(
            "local-tools", "shopify_update_inventory", {}, {"workspace_id": "ws"}
        )
        assert "Failed to update inventory: nope" in result

    @pytest.mark.asyncio
    async def test_shopify_get_orders(self, svc, monkeypatch):
        db = MagicMock()
        store = MagicMock()
        store.access_token = "tok"
        store.shop_domain = "shop"
        db.query.return_value.filter.return_value.first.return_value = store
        monkeypatch.setattr(
            "core.database.SessionLocal", _session_factory(db)
        )
        service = MagicMock()
        service.get_orders = AsyncMock(
            return_value=[
                {
                    "order_number": 1,
                    "total_price": "10.00",
                    "currency": "USD",
                    "financial_status": "paid",
                }
            ]
        )
        monkeypatch.setattr(
            "integrations.shopify_service.ShopifyService", lambda: service
        )
        result = await svc.execute_tool(
            "local-tools", "shopify_get_orders", {}, {"workspace_id": "ws"}
        )
        assert "Order #1: 10.00 USD (paid)" in result

    @pytest.mark.asyncio
    async def test_shopify_get_orders_empty(self, svc, monkeypatch):
        db = MagicMock()
        store = MagicMock()
        store.access_token = "tok"
        store.shop_domain = "shop"
        db.query.return_value.filter.return_value.first.return_value = store
        monkeypatch.setattr(
            "core.database.SessionLocal", _session_factory(db)
        )
        service = MagicMock()
        service.get_orders = AsyncMock(return_value=[])
        monkeypatch.setattr(
            "integrations.shopify_service.ShopifyService", lambda: service
        )
        result = await svc.execute_tool(
            "local-tools", "shopify_get_orders", {}, {"workspace_id": "ws"}
        )
        assert result == "No orders found."

    @pytest.mark.asyncio
    async def test_reconcile_payroll(self, svc, monkeypatch):
        agent = MagicMock()
        agent.reconcile_payroll = AsyncMock(return_value="payroll done")
        monkeypatch.setattr(
            "finance.automations.payroll_guardian.PayrollReconciliationWorkflow",
            lambda: agent,
        )
        result = await svc.execute_tool(
            "local-tools", "reconcile_payroll", {"period": "2026-07"}, {}
        )
        assert result == "payroll done"

    @pytest.mark.asyncio
    async def test_list_agents(self, svc, monkeypatch):
        db = MagicMock()
        agent1 = MagicMock()
        agent1.id = "a1"
        agent1.name = "Agent One"
        agent1.description = "d"
        agent1.category = "general"
        db.query.return_value.all.return_value = [agent1]
        monkeypatch.setattr(
            "core.database.SessionLocal", _session_factory(db)
        )
        result = await svc.execute_tool("local-tools", "list_agents", {}, {})
        assert result["registered"] == [
            {"id": "a1", "name": "Agent One", "description": "d", "category": "general"}
        ]
        assert isinstance(result["templates"], dict)

    @pytest.mark.asyncio
    async def test_spawn_agent(self, svc, monkeypatch):
        atom = MagicMock()
        atom.spawn_agent = AsyncMock(return_value={"spawned": True})
        monkeypatch.setattr("core.atom_meta_agent.get_atom_agent", lambda ws: atom)
        result = await svc.execute_tool(
            "local-tools", "spawn_agent", {"template": "researcher"}, {"workspace_id": "ws"}
        )
        assert result == {"spawned": True}

    @pytest.mark.asyncio
    async def test_list_workflows_no_dir(self, svc, monkeypatch):
        monkeypatch.setattr("integrations.mcp_service.os.path.exists", lambda p: False)
        result = await svc.execute_tool("local-tools", "list_workflows", {}, {})
        assert result == []

    @pytest.mark.asyncio
    async def test_list_workflows_exception(self, svc, monkeypatch):
        monkeypatch.setattr("integrations.mcp_service.os.path.exists", lambda p: True)

        def _listdir(p):
            raise OSError("boom")

        monkeypatch.setattr("integrations.mcp_service.os.listdir", _listdir)
        result = await svc.execute_tool("local-tools", "list_workflows", {}, {})
        assert result == []

    @pytest.mark.asyncio
    async def test_bridge_agent_delegate_missing_args(self, svc):
        result = await svc.execute_tool("local-tools", "bridge_agent_delegate", {}, {})
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_bridge_agent_delegate_success(self, svc, monkeypatch):
        bridge = MagicMock()
        bridge.process_incoming_message = AsyncMock(return_value={"delivered": True})
        monkeypatch.setattr(
            "integrations.universal_webhook_bridge.universal_webhook_bridge", bridge
        )
        result = await svc.execute_tool(
            "local-tools",
            "bridge_agent_delegate",
            {"target_agent": "ag-1", "message": "hi"},
            {"agent_id": "a1"},
        )
        assert result == {"delivered": True}

    @pytest.mark.asyncio
    async def test_unknown_local_tool(self, svc):
        result = await svc.execute_tool("local-tools", "not_a_real_tool", {}, {})
        assert result["status"] == "not_implemented"


# ============================================================================
# execute_tool: browser tools
# ============================================================================


class TestExecuteToolBrowser:
    @pytest.fixture(autouse=True)
    def _neutralize_registry(self, monkeypatch):
        _no_registry(monkeypatch)

    @pytest.mark.asyncio
    async def test_browser_navigate_desktop_sent(self, svc, monkeypatch):
        nm = MagicMock()
        nm.send_to_desktop = AsyncMock(return_value=True)
        monkeypatch.setattr("core.notification_manager.notification_manager", nm)
        result = await svc.execute_tool(
            "local-tools", "browser_navigate", {"url": "http://x"}, {}
        )
        assert "Command sent to Desktop App: Navigate to http://x" in result

    @pytest.mark.asyncio
    async def test_browser_navigate_desktop_unsent_simulation(self, svc, monkeypatch):
        nm = MagicMock()
        nm.send_to_desktop = AsyncMock(return_value=False)
        monkeypatch.setattr("core.notification_manager.notification_manager", nm)
        result = await svc.execute_tool(
            "local-tools", "browser_navigate", {"url": "http://x"}, {}
        )
        assert "[SIMULATION]" in result

    @pytest.mark.asyncio
    async def test_browser_navigate_cloud_restricted(self, svc, monkeypatch):
        ws = MagicMock()
        ws.tenant_id = "t"
        tenant = MagicMock()
        tenant.plan_type = "PRO"
        db = MagicMock()
        db.query.side_effect = [
            _query_first(value=ws),
            _query_first(value=tenant),
        ]
        monkeypatch.setattr("core.database.SessionLocal", _session_factory(db))
        result = await svc.execute_tool(
            "local-tools",
            "browser_navigate",
            {"url": "http://x"},
            {"computer_use_mode": "cloud", "workspace_id": "ws-1"},
        )
        assert "Enterprise" in result

    @pytest.mark.asyncio
    async def test_browser_cloud_import_error(self, svc, monkeypatch):
        monkeypatch.setitem(sys.modules, "core.cloud_browser_service", None)
        result = await svc.execute_tool(
            "local-tools",
            "browser_navigate",
            {"url": "http://x"},
            {"computer_use_mode": "cloud", "workspace_id": "default"},
        )
        assert "Cloud browser service not available" in result

    @pytest.mark.asyncio
    async def test_browser_click_desktop(self, svc, monkeypatch):
        nm = MagicMock()
        nm.send_to_desktop = AsyncMock(return_value=True)
        monkeypatch.setattr("core.notification_manager.notification_manager", nm)
        result = await svc.execute_tool(
            "local-tools", "browser_click", {"selector": "#a", "x": 1, "y": 2}, {}
        )
        assert "Click #a" in result

    @pytest.mark.asyncio
    async def test_browser_type_desktop_unsent(self, svc, monkeypatch):
        nm = MagicMock()
        nm.send_to_desktop = AsyncMock(return_value=False)
        monkeypatch.setattr("core.notification_manager.notification_manager", nm)
        result = await svc.execute_tool(
            "local-tools", "browser_type", {"text": "hi", "selector": "#b"}, {}
        )
        assert "[SIMULATION] Typed 'hi'" in result

    @pytest.mark.asyncio
    async def test_browser_screenshot_desktop_sent(self, svc, monkeypatch):
        nm = MagicMock()
        nm.send_to_desktop = AsyncMock(return_value=True)
        monkeypatch.setattr("core.notification_manager.notification_manager", nm)
        result = await svc.execute_tool("local-tools", "browser_screenshot", {}, {})
        assert "Screenshot requested" in result

    @pytest.mark.asyncio
    async def test_browser_screenshot_desktop_unsent(self, svc, monkeypatch):
        nm = MagicMock()
        nm.send_to_desktop = AsyncMock(return_value=False)
        monkeypatch.setattr("core.notification_manager.notification_manager", nm)
        result = await svc.execute_tool("local-tools", "browser_screenshot", {}, {})
        assert "[SIMULATION] Screenshot captured" in result

    @pytest.mark.asyncio
    async def test_browser_cloud_only_tools_desktop_error(self, svc):
        ctx = {"computer_use_mode": "desktop"}
        tools = [
            "browser_new_tab",
            "browser_switch_tab",
            "browser_click_coords",
            "list_browser_tabs",
            "browser_save_session",
            "browser_set_proxy",
            "browser_monitor",
            "browser_wait_for_selector",
            "browser_extract_content",
            "browser_upload_file",
            "browser_download_file",
        ]
        for tool in tools:
            result = await svc.execute_tool("local-tools", tool, {}, ctx)
            assert "only available in cloud mode" in result or "Error:" in result

    @pytest.mark.asyncio
    async def test_browser_cloud_only_tools_cloud_import_error(self, svc, monkeypatch):
        monkeypatch.setitem(sys.modules, "core.cloud_browser_service", None)
        ctx = {"computer_use_mode": "cloud", "workspace_id": "default"}
        tools = [
            "browser_new_tab",
            "browser_switch_tab",
            "browser_click_coords",
            "list_browser_tabs",
            "browser_save_session",
            "browser_set_proxy",
            "browser_monitor",
            "browser_wait_for_selector",
            "browser_extract_content",
            "browser_upload_file",
            "browser_download_file",
        ]
        for tool in tools:
            result = await svc.execute_tool("local-tools", tool, {}, ctx)
            assert "Cloud browser service not available" in result

    @pytest.mark.asyncio
    async def test_browser_click_cloud_import_error(self, svc, monkeypatch):
        monkeypatch.setitem(sys.modules, "core.cloud_browser_service", None)
        result = await svc.execute_tool(
            "local-tools",
            "browser_click",
            {"selector": "#a"},
            {"computer_use_mode": "cloud", "workspace_id": "default"},
        )
        assert "Cloud browser service not available" in result

    @pytest.mark.asyncio
    async def test_browser_type_cloud_import_error(self, svc, monkeypatch):
        monkeypatch.setitem(sys.modules, "core.cloud_browser_service", None)
        result = await svc.execute_tool(
            "local-tools",
            "browser_type",
            {"text": "hi"},
            {"computer_use_mode": "cloud", "workspace_id": "default"},
        )
        assert "Cloud browser service not available" in result

    @pytest.mark.asyncio
    async def test_browser_screenshot_cloud_import_error(self, svc, monkeypatch):
        monkeypatch.setitem(sys.modules, "core.cloud_browser_service", None)
        result = await svc.execute_tool(
            "local-tools",
            "browser_screenshot",
            {},
            {"computer_use_mode": "cloud", "workspace_id": "default"},
        )
        assert "Cloud browser service not available" in result


# ============================================================================
# execute_tool: CRM / sales / universal-integration tools
# ============================================================================


class TestExecuteToolUniversal:
    @pytest.fixture(autouse=True)
    def _neutralize_registry(self, monkeypatch):
        _no_registry(monkeypatch)

    @pytest.mark.asyncio
    async def test_search_contacts_with_platform(self, svc, monkeypatch):
        cls, inst = _fake_universal_cls(search_result={"status": "success"})
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools", "search_contacts", {"platform": "hubspot", "query": "q"}, {}
        )
        assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_search_contacts_all_providers_fail(self, svc, monkeypatch):
        inst = MagicMock()
        inst.search = AsyncMock(side_effect=RuntimeError("down"))
        cls = MagicMock(return_value=inst)
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools", "search_contacts", {"query": "q"}, {}
        )
        assert result == {}

    @pytest.mark.asyncio
    async def test_create_crm_lead_no_platform(self, svc):
        result = await svc.execute_tool("local-tools", "create_crm_lead", {}, {})
        assert result == {"error": "platform is required"}

    @pytest.mark.asyncio
    async def test_create_crm_lead_success(self, svc, monkeypatch):
        cls, inst = _fake_universal_cls(execute_result={"status": "success"})
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools",
            "create_crm_lead",
            {"platform": "salesforce", "first_name": "F"},
            {},
        )
        assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_get_sales_pipeline_both_platforms(self, svc, monkeypatch):
        inst = MagicMock()
        inst.execute = AsyncMock(
            side_effect=[
                {
                    "status": "success",
                    "data": [{"Name": "Deal A", "Amount": 100, "StageName": "Prospecting"}],
                },
                {
                    "status": "success",
                    "data": [
                        {
                            "properties": {
                                "dealname": "Deal B",
                                "amount": "50",
                                "dealstage": "appointment",
                            }
                        }
                    ],
                },
            ]
        )
        cls = MagicMock(return_value=inst)
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool("local-tools", "get_sales_pipeline", {}, {})
        assert result == [
            {"deal": "Deal A", "value": 100, "status": "Prospecting", "platform": "salesforce"},
            {"deal": "Deal B", "value": 50.0, "status": "appointment", "platform": "hubspot"},
        ]

    @pytest.mark.asyncio
    async def test_get_sales_pipeline_provider_error(self, svc, monkeypatch):
        inst = MagicMock()
        inst.execute = AsyncMock(side_effect=RuntimeError("api down"))
        cls = MagicMock(return_value=inst)
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools", "get_sales_pipeline", {"platform": "salesforce"}, {}
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_get_tasks_with_platform(self, svc, monkeypatch):
        cls, inst = _fake_universal_cls(execute_result={"status": "success"})
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools", "get_tasks", {"platform": "jira"}, {}
        )
        assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_get_tasks_all_providers_fail(self, svc, monkeypatch):
        inst = MagicMock()
        inst.execute = AsyncMock(side_effect=RuntimeError("down"))
        cls = MagicMock(return_value=inst)
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool("local-tools", "get_tasks", {}, {})
        assert result == {}

    @pytest.mark.asyncio
    async def test_search_tasks_with_platform(self, svc, monkeypatch):
        cls, inst = _fake_universal_cls(search_result={"status": "success"})
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools", "search_tasks", {"platform": "linear", "query": "q"}, {}
        )
        assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_create_task_with_platform(self, svc, monkeypatch):
        cls, inst = _fake_universal_cls(execute_result={"status": "success"})
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools", "create_task", {"platform": "asana", "project": "p"}, {}
        )
        assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_create_task_no_platform_finds_connection(self, svc, monkeypatch):
        cls, inst = _fake_universal_cls(execute_result={"status": "success"})
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        conn = MagicMock()
        conn.piece_name = "jira"
        conn_cls = MagicMock()
        conn_cls.return_value.list_connections = AsyncMock(return_value=[conn])
        monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)
        result = await svc.execute_tool(
            "local-tools", "create_task", {"project": "p"}, {"user_id": "u"}
        )
        assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_create_task_no_platform_no_connection(self, svc, monkeypatch):
        conn_cls = MagicMock()
        conn_cls.return_value.list_connections = AsyncMock(return_value=[])
        monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)
        result = await svc.execute_tool(
            "local-tools", "create_task", {"project": "p"}, {"user_id": "u"}
        )
        assert result == {"error": "No project management platform connected."}

    @pytest.mark.asyncio
    async def test_list_projects_no_platform(self, svc):
        result = await svc.execute_tool("local-tools", "list_projects", {}, {})
        assert result == {"error": "platform is required"}

    @pytest.mark.asyncio
    async def test_list_projects_success(self, svc, monkeypatch):
        cls, inst = _fake_universal_cls(execute_result={"status": "success"})
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools", "list_projects", {"platform": "asana"}, {}
        )
        assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_send_message_hitl_intercepts(self, svc, monkeypatch):
        monkeypatch.setattr(
            svc, "_check_hitl_policy", AsyncMock(return_value={"paused": True})
        )
        result = await svc.execute_tool(
            "local-tools", "send_message", {"target": "t", "message": "m"}, {}
        )
        assert result == {"paused": True}

    @pytest.mark.asyncio
    async def test_send_message_no_connection(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "_check_hitl_policy", AsyncMock(return_value=None))
        conn_cls = MagicMock()
        conn_cls.return_value.list_connections = AsyncMock(return_value=[])
        monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)
        result = await svc.execute_tool(
            "local-tools", "send_message", {"target": "t", "message": "m"}, {"user_id": "u"}
        )
        assert result == {"error": "No communication platform connected."}

    @pytest.mark.asyncio
    async def test_send_message_success(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "_check_hitl_policy", AsyncMock(return_value=None))
        conn = MagicMock()
        conn.piece_name = "slack"
        conn_cls = MagicMock()
        conn_cls.return_value.list_connections = AsyncMock(return_value=[conn])
        monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)
        cls, inst = _fake_universal_cls(execute_result={"status": "sent"})
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools", "send_message", {"target": "t", "message": "m"}, {"user_id": "u"}
        )
        assert result == {"status": "sent"}

    @pytest.mark.asyncio
    async def test_post_channel_message_no_platform(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "_check_hitl_policy", AsyncMock(return_value=None))
        result = await svc.execute_tool(
            "local-tools", "post_channel_message", {"channel": "c"}, {}
        )
        assert result == {"error": "platform is required"}

    @pytest.mark.asyncio
    async def test_post_channel_message_success(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "_check_hitl_policy", AsyncMock(return_value=None))
        cls, inst = _fake_universal_cls(execute_result={"status": "sent"})
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools",
            "post_channel_message",
            {"platform": "teams", "channel": "c", "message": "m"},
            {},
        )
        assert result == {"status": "sent"}

    @pytest.mark.asyncio
    async def test_send_email(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "_check_hitl_policy", AsyncMock(return_value=None))
        cls, inst = _fake_universal_cls(execute_result={"status": "sent"})
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools", "send_email", {"to": "x@y", "subject": "s", "body": "b"}, {}
        )
        assert result == {"status": "sent"}

    @pytest.mark.asyncio
    async def test_search_emails_with_platform(self, svc, monkeypatch):
        cls, inst = _fake_universal_cls(execute_result={"status": "success"})
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools", "search_emails", {"platform": "gmail", "query": "q"}, {}
        )
        assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_search_emails_default_gmail(self, svc, monkeypatch):
        cls, inst = _fake_universal_cls(execute_result={"status": "success"})
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools", "search_emails", {"query": "q"}, {}
        )
        assert result == {"gmail": {"status": "success"}}

    @pytest.mark.asyncio
    async def test_unified_communication_search_all_fail(self, svc, monkeypatch):
        inst = MagicMock()
        inst.search = AsyncMock(side_effect=RuntimeError("down"))
        cls = MagicMock(return_value=inst)
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools", "unified_communication_search", {"query": "q"}, {}
        )
        assert result == {}

    @pytest.mark.asyncio
    async def test_list_calendar_events(self, svc, monkeypatch):
        cls, inst = _fake_universal_cls(execute_result={"status": "success"})
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool("local-tools", "list_calendar_events", {}, {})
        assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_create_calendar_event(self, svc, monkeypatch):
        cls, inst = _fake_universal_cls(execute_result={"status": "success"})
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools", "create_calendar_event", {"title": "Meet"}, {}
        )
        assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_search_files_all_providers_fail(self, svc, monkeypatch):
        inst = MagicMock()
        inst.search = AsyncMock(side_effect=RuntimeError("down"))
        cls = MagicMock(return_value=inst)
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools", "search_files", {"query": "q"}, {}
        )
        assert result == {}

    @pytest.mark.asyncio
    async def test_list_files_no_platform(self, svc):
        result = await svc.execute_tool("local-tools", "list_files", {}, {})
        assert result == {"error": "platform is required"}

    @pytest.mark.asyncio
    async def test_list_files_success(self, svc, monkeypatch):
        cls, inst = _fake_universal_cls(execute_result={"status": "success"})
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools", "list_files", {"platform": "drive"}, {}
        )
        assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_create_folder_no_platform(self, svc):
        result = await svc.execute_tool("local-tools", "create_folder", {}, {})
        assert result == {"error": "platform is required"}

    @pytest.mark.asyncio
    async def test_create_folder_success(self, svc, monkeypatch):
        cls, inst = _fake_universal_cls(execute_result={"status": "success"})
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools", "create_folder", {"platform": "dropbox", "name": "n"}, {}
        )
        assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_search_tickets_all_providers_fail(self, svc, monkeypatch):
        inst = MagicMock()
        inst.search = AsyncMock(side_effect=RuntimeError("down"))
        cls = MagicMock(return_value=inst)
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools", "search_tickets", {"query": "q"}, {}
        )
        assert result == {}

    @pytest.mark.asyncio
    async def test_create_ticket_no_platform(self, svc):
        result = await svc.execute_tool("local-tools", "create_ticket", {}, {})
        assert result == {"error": "platform is required"}

    @pytest.mark.asyncio
    async def test_search_repositories_all_providers_fail(self, svc, monkeypatch):
        inst = MagicMock()
        inst.search = AsyncMock(side_effect=RuntimeError("down"))
        cls = MagicMock(return_value=inst)
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools", "search_repositories", {"query": "q"}, {}
        )
        assert result == {}

    @pytest.mark.asyncio
    async def test_search_designs(self, svc, monkeypatch):
        cls, inst = _fake_universal_cls(search_result={"status": "success"})
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools", "search_designs", {"query": "q"}, {}
        )
        assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_query_financial_metrics(self, svc, monkeypatch):
        cls, inst = _fake_universal_cls(execute_result={"status": "success"})
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools", "query_financial_metrics", {"period": "2026-07"}, {}
        )
        assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_list_finance_invoices_all_providers_fail(self, svc, monkeypatch):
        inst = MagicMock()
        inst.execute = AsyncMock(side_effect=RuntimeError("down"))
        cls = MagicMock(return_value=inst)
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool("local-tools", "list_finance_invoices", {}, {})
        assert result == {}

    @pytest.mark.asyncio
    async def test_search_dashboards_all_providers_fail(self, svc, monkeypatch):
        inst = MagicMock()
        inst.search = AsyncMock(side_effect=RuntimeError("down"))
        cls = MagicMock(return_value=inst)
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools", "search_dashboards", {"query": "q"}, {}
        )
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_inventory_levels_no_connections(self, svc, monkeypatch):
        conn_cls = MagicMock()
        conn_cls.return_value.list_connections = AsyncMock(return_value=[])
        monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)
        result = await svc.execute_tool(
            "local-tools", "get_inventory_levels", {}, {"user_id": "u"}
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_create_zoom_meeting_no_connection(self, svc, monkeypatch):
        conn_cls = MagicMock()
        conn_cls.return_value.list_connections = AsyncMock(return_value=[])
        monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)
        with pytest.raises(ImportError):
            await svc.execute_tool(
                "local-tools", "create_zoom_meeting", {}, {"user_id": "u"}
            )

    @pytest.mark.asyncio
    async def test_create_zoom_meeting_with_connection(self, svc, monkeypatch):
        conn = MagicMock()
        conn.piece_name = "zoom"
        conn.credentials = {"access_token": "t"}
        conn_cls = MagicMock()
        conn_cls.return_value.list_connections = AsyncMock(return_value=[conn])
        monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)
        zoom = MagicMock()
        zoom.create_meeting = AsyncMock(return_value={"id": "m1"})
        monkeypatch.setattr("integrations.zoom_service.ZoomService", lambda **kw: zoom)
        result = await svc.execute_tool(
            "local-tools", "create_zoom_meeting", {}, {"user_id": "u"}
        )
        assert result == {"id": "m1"}

    @pytest.mark.asyncio
    async def test_get_system_health_with_service(self, svc, monkeypatch):
        cb = MagicMock()
        cb.get_stats = MagicMock(return_value={"failures": 0})
        monkeypatch.setattr("core.circuit_breaker.circuit_breaker", cb)
        analytics = MagicMock()
        analytics.analyze_service_drift = MagicMock(return_value={"drift": 0.1})
        monkeypatch.setattr("core.analytics_engine.get_analytics_engine", lambda: analytics)
        result = await svc.execute_tool(
            "local-tools", "get_system_health", {"service": "shopify"}, {}
        )
        assert result == {"stats": {"failures": 0}, "drift": {"drift": 0.1}}

    @pytest.mark.asyncio
    async def test_get_system_health_global(self, svc, monkeypatch):
        cb = MagicMock()
        cb.get_all_stats = MagicMock(return_value={"all": 1})
        monkeypatch.setattr("core.circuit_breaker.circuit_breaker", cb)
        analytics = MagicMock()
        analytics.get_global_performance_report = MagicMock(return_value={"ok": True})
        monkeypatch.setattr("core.analytics_engine.get_analytics_engine", lambda: analytics)
        result = await svc.execute_tool("local-tools", "get_system_health", {}, {})
        assert result == {"circuit_breaker": {"all": 1}, "global_report": {"ok": True}}

    @pytest.mark.asyncio
    async def test_generate_pdf_report(self, svc, monkeypatch):
        pdf = MagicMock()
        pdf_cls = MagicMock(return_value=pdf)
        monkeypatch.setattr("fpdf.FPDF", pdf_cls)
        result = await svc.execute_tool(
            "local-tools",
            "generate_pdf_report",
            {"content": "line1\nline2", "filename": "/etc/cron.d/evil_report"},
            {},
        )
        assert result["file_path"].startswith("/tmp/")
        assert result["file_path"].endswith("evil_report.pdf")
        pdf.output.assert_called_once()

    @pytest.mark.asyncio
    async def test_manage_reviews(self, svc, monkeypatch):
        agent = MagicMock()
        agent.manage_google_reviews = AsyncMock(return_value="reviews")
        monkeypatch.setattr("core.marketing_agent.MarketingAgent", lambda: agent)
        result = await svc.execute_tool(
            "local-tools", "manage_reviews", {}, {"workspace_id": "ws"}
        )
        assert result == "reviews"

    @pytest.mark.asyncio
    async def test_request_testimonial(self, svc, monkeypatch):
        agent = MagicMock()
        agent.request_testimonial = AsyncMock(return_value="sent")
        monkeypatch.setattr("core.marketing_agent.MarketingAgent", lambda: agent)
        result = await svc.execute_tool(
            "local-tools",
            "request_testimonial",
            {"customer_id": "c1", "platform": "email"},
            {"workspace_id": "ws"},
        )
        assert result == "sent"

    @pytest.mark.asyncio
    async def test_analyze_ads_performance(self, svc, monkeypatch):
        agent = MagicMock()
        agent.run_ads_check = AsyncMock(return_value="ads")
        monkeypatch.setattr("core.marketing_agent.MarketingAgent", lambda: agent)
        result = await svc.execute_tool(
            "local-tools",
            "analyze_ads_performance",
            {"service": "meta_ads"},
            {"workspace_id": "ws"},
        )
        assert result == "ads"

    @pytest.mark.asyncio
    async def test_sales_lead_tools_import_error(self, svc, monkeypatch):
        monkeypatch.setitem(sys.modules, "core.sales_agent", None)
        for tool in ["score_lead", "draft_sales_outreach", "monitor_pipeline_health"]:
            result = await svc.execute_tool(
                "local-tools", tool, {"lead_data": {}}, {"workspace_id": "ws"}
            )
            assert "Sales agent service not available" in result["error"]

    @pytest.mark.asyncio
    async def test_shipping_no_platform_no_connection(self, svc, monkeypatch):
        conn_cls = MagicMock()
        conn_cls.return_value.list_connections = AsyncMock(return_value=[])
        monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)
        result = await svc.execute_tool(
            "local-tools", "create_shipment", {"to_address": {}}, {"user_id": "u"}
        )
        assert "No shipping platform connected" in result["error"]

    @pytest.mark.asyncio
    async def test_shipping_with_platform(self, svc, monkeypatch):
        cls, inst = _fake_universal_cls(execute_result={"status": "success"})
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools",
            "create_shipment",
            {"platform": "shippo", "to_address": {}},
            {},
        )
        assert result == {"status": "success"}
        assert inst.execute.await_args.args[1] == "create_shipment"

    @pytest.mark.asyncio
    async def test_shipping_rates_action_map(self, svc, monkeypatch):
        cls, inst = _fake_universal_cls(execute_result={"status": "success"})
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool(
            "local-tools", "get_shipping_rates", {"platform": "easypost"}, {}
        )
        assert result == {"status": "success"}
        assert inst.execute.await_args.args[1] == "get_rates"

    @pytest.mark.asyncio
    async def test_cloud_provider_tools(self, svc, monkeypatch):
        cls, inst = _fake_universal_cls(execute_result={"status": "success"})
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        assert await svc.execute_tool("local-tools", "s3_upload", {"bucket": "b"}, {}) == {"status": "success"}
        assert inst.execute.await_args.args[0] == "aws"
        assert await svc.execute_tool("local-tools", "azure_blob_upload", {}, {}) == {"status": "success"}
        assert inst.execute.await_args.args[0] == "azure"
        assert await svc.execute_tool("local-tools", "gcs_upload", {}, {}) == {"status": "success"}
        assert inst.execute.await_args.args[0] == "gcp"

    @pytest.mark.asyncio
    async def test_unified_knowledge_search_empty_entities(self, svc, monkeypatch):
        engine = MagicMock()
        engine.entity_registry.values.return_value = []
        monkeypatch.setattr("ai.data_intelligence.DataIntelligenceEngine", lambda: engine)
        result = await svc.execute_tool(
            "local-tools", "unified_knowledge_search", {"query": "q"}, {}
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_save_business_fact(self, svc, monkeypatch):
        wm = MagicMock()
        wm.record_business_fact = AsyncMock(return_value=True)
        wm_cls = MagicMock(return_value=wm)
        monkeypatch.setattr("core.agent_world_model.WorldModelService", wm_cls)
        fact_cls = MagicMock()
        fact = fact_cls.return_value
        fact.fact = "customers prefer X"
        monkeypatch.setattr("core.agent_world_model.BusinessFact", fact_cls)
        result = await svc.execute_tool(
            "local-tools",
            "save_business_fact",
            {"fact": "customers prefer X", "citations": ["/tmp/a"], "source": "email"},
            {"workspace_id": "ws", "agent_id": "a1"},
        )
        assert result == "Fact saved: customers prefer X"
        wm.record_business_fact.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_business_fact_failure(self, svc, monkeypatch):
        wm = MagicMock()
        wm.record_business_fact = AsyncMock(return_value=False)
        wm_cls = MagicMock(return_value=wm)
        monkeypatch.setattr("core.agent_world_model.WorldModelService", wm_cls)
        fact_cls = MagicMock()
        fact = fact_cls.return_value
        fact.fact = "fact"
        monkeypatch.setattr("core.agent_world_model.BusinessFact", fact_cls)
        result = await svc.execute_tool(
            "local-tools", "save_business_fact", {"fact": "fact"}, {}
        )
        assert result == "Failed to save fact."

    @pytest.mark.asyncio
    async def test_verify_citation_allowed(self, svc, tmp_path):
        path = "/tmp/covpush_verify_citation.txt"
        try:
            with open(path, "w") as f:
                f.write("hello citation")
            result = await svc.execute_tool(
                "local-tools", "verify_citation", {"path": path}, {}
            )
            assert result.startswith("Verified:")
            assert "hello citation" in result
        finally:
            if os.path.exists(path):
                os.remove(path)

    @pytest.mark.asyncio
    async def test_verify_citation_not_found(self, svc, monkeypatch):
        monkeypatch.setattr("integrations.mcp_service.os.path.exists", lambda p: False)
        result = await svc.execute_tool(
            "local-tools", "verify_citation", {"path": "/tmp/does_not_exist.txt"}, {}
        )
        assert "NOT found" in result

    @pytest.mark.asyncio
    async def test_verify_citation_read_error(self, svc, monkeypatch):
        monkeypatch.setattr("integrations.mcp_service.os.path.exists", lambda p: True)

        def _open(*a, **k):
            raise OSError("unreadable")

        monkeypatch.setattr("builtins.open", _open)
        result = await svc.execute_tool(
            "local-tools", "verify_citation", {"path": "/tmp/x.txt"}, {}
        )
        assert "failed to read" in result

    @pytest.mark.asyncio
    async def test_ingest_knowledge_from_text_no_text(self, svc):
        result = await svc.execute_tool("local-tools", "ingest_knowledge_from_text", {}, {})
        assert result == {"error": "Text content is required"}

    @pytest.mark.asyncio
    async def test_ingest_knowledge_from_text_success(self, svc, monkeypatch):
        manager = MagicMock()
        manager.process_document = AsyncMock(return_value={"pages": 1})
        monkeypatch.setattr("core.knowledge_ingestion.get_knowledge_ingestion", lambda: manager)
        result = await svc.execute_tool(
            "local-tools",
            "ingest_knowledge_from_text",
            {"text": "some text", "doc_id": "d1", "source": "s1"},
            {"workspace_id": "ws", "user_id": "u"},
        )
        assert result == {"success": True, "stats": {"pages": 1}}

    @pytest.mark.asyncio
    async def test_ingest_knowledge_from_file_no_path(self, svc):
        result = await svc.execute_tool("local-tools", "ingest_knowledge_from_file", {}, {})
        assert result == {"error": "File path is required"}

    @pytest.mark.asyncio
    async def test_ingest_knowledge_from_file_missing(self, svc, monkeypatch):
        monkeypatch.setattr("integrations.mcp_service.os.path.exists", lambda p: False)
        result = await svc.execute_tool(
            "local-tools", "ingest_knowledge_from_file", {"file_path": "/tmp/nope.txt"}, {}
        )
        assert "File not found" in result["error"]

    @pytest.mark.asyncio
    async def test_ingest_knowledge_from_file_success(self, svc, monkeypatch):
        path = "/tmp/covpush_ingest.txt"
        try:
            with open(path, "w") as f:
                f.write("document text")
            monkeypatch.setattr("integrations.mcp_service.os.path.exists", lambda p: True)
            processor = MagicMock()
            processor.process_document = AsyncMock(
                return_value={
                    "success": True,
                    "content": "document text",
                    "page_count": 1,
                    "total_chars": 13,
                    "tables": [{"t": 1}],
                }
            )
            monkeypatch.setattr("core.docling_processor.get_docling_processor", lambda: processor)
            manager = MagicMock()
            manager.process_document = AsyncMock(return_value={"entities": 2})
            monkeypatch.setattr("core.knowledge_ingestion.get_knowledge_ingestion", lambda: manager)
            result = await svc.execute_tool(
                "local-tools",
                "ingest_knowledge_from_file",
                {"file_path": path},
                {"workspace_id": "ws", "user_id": "u"},
            )
            assert result["success"] is True
            assert result["file_stats"]["tables_found"] == 1
            assert result["file_stats"]["formulas_extracted"] == 0
        finally:
            if os.path.exists(path):
                os.remove(path)

    @pytest.mark.asyncio
    async def test_ingest_knowledge_from_file_parse_failure(self, svc, monkeypatch):
        monkeypatch.setattr("integrations.mcp_service.os.path.exists", lambda p: True)
        processor = MagicMock()
        processor.process_document = AsyncMock(return_value={"success": False, "error": "bad doc"})
        monkeypatch.setattr("core.docling_processor.get_docling_processor", lambda: processor)
        result = await svc.execute_tool(
            "local-tools", "ingest_knowledge_from_file", {"file_path": "/tmp/x.pdf"}, {}
        )
        assert "File parsing failed" in result["error"]

    @pytest.mark.asyncio
    async def test_ingest_knowledge_from_file_no_content(self, svc, monkeypatch):
        monkeypatch.setattr("integrations.mcp_service.os.path.exists", lambda p: True)
        processor = MagicMock()
        processor.process_document = AsyncMock(return_value={"success": True, "content": ""})
        monkeypatch.setattr("core.docling_processor.get_docling_processor", lambda: processor)
        result = await svc.execute_tool(
            "local-tools", "ingest_knowledge_from_file", {"file_path": "/tmp/x.pdf"}, {}
        )
        assert result == {"error": "No content extracted from file"}

    @pytest.mark.asyncio
    async def test_search_formulas_no_query(self, svc):
        with pytest.raises(TypeError):
            await svc.execute_tool("local-tools", "search_formulas", {}, {})

    @pytest.mark.asyncio
    async def test_search_formulas_success(self, svc, monkeypatch):
        manager = MagicMock()
        manager.search_formulas = MagicMock(return_value=[{"name": "f1"}])
        monkeypatch.setattr("core.formula_memory.get_formula_manager", lambda **kw: manager)
        result = await svc.execute_tool(
            "local-tools", "search_formulas", {"query": "revenue"}, {"user_id": "u"}
        )
        assert result == {"results": [{"name": "f1"}]}

    @pytest.mark.asyncio
    async def test_query_knowledge_graph_no_query(self, svc):
        result = await svc.execute_tool("local-tools", "query_knowledge_graph", {}, {})
        assert result == {"error": "Search query is required"}

    @pytest.mark.asyncio
    async def test_query_knowledge_graph_success(self, svc, monkeypatch):
        manager = MagicMock()
        manager.query_graphrag = MagicMock(return_value={"answer": "yes"})
        monkeypatch.setattr("core.knowledge_ingestion.get_knowledge_ingestion", lambda: manager)
        result = await svc.execute_tool(
            "local-tools", "query_knowledge_graph", {"query": "q", "mode": "local"}, {}
        )
        assert result == {"answer": "yes"}

    @pytest.mark.asyncio
    async def test_standardized_tools(self, svc, monkeypatch):
        singleton = MagicMock()
        singleton.execute = AsyncMock(return_value={"status": "success"})
        monkeypatch.setattr(
            "integrations.universal_integration_service.universal_integration_service",
            singleton,
        )
        cases = [
            ("update_crm_lead", {"platform": "sf", "id": "1", "data": {}}),
            ("create_crm_deal", {"platform": "sf", "data": {}}),
            ("update_crm_deal", {"platform": "sf", "id": "1", "data": {}}),
            ("update_task", {"platform": "jira", "id": "1", "data": {}}),
            ("create_support_ticket", {"platform": "zd"}),
            ("update_support_ticket", {"platform": "zd", "id": "1"}),
            ("create_ecommerce_order", {"platform": "shopify"}),
            ("upload_file_to_storage", {"platform": "gdrive"}),
            ("create_storage_folder", {"platform": "gdrive"}),
            ("add_marketing_subscriber", {"platform": "mailchimp"}),
            ("create_invoice", {"platform": "stripe"}),
            ("create_record", {"service": "sf", "entity": "lead", "data": {}}),
            ("update_record", {"service": "sf", "entity": "lead", "id": "1"}),
            ("push_to_integration", {"service": "sf", "action": "sync", "params": {}}),
        ]
        for tool, args in cases:
            result = await svc.execute_tool("local-tools", tool, args, {})
            assert result == {"status": "success"}, tool
        assert singleton.execute.await_count == len(cases)

    @pytest.mark.asyncio
    async def test_discover_connections(self, svc, monkeypatch):
        conn_service = MagicMock()
        conn_service.get_connections = MagicMock(
            return_value=[
                {"integration_id": "slack", "status": "active"},
                {"integration_id": "gmail", "status": "revoked"},
            ]
        )
        monkeypatch.setattr("core.connection_service.connection_service", conn_service)
        result = await svc.execute_tool(
            "local-tools", "discover_connections", {}, {"user_id": "u"}
        )
        assert result == {"active_integrations": ["slack"]}

    @pytest.mark.asyncio
    async def test_global_search_with_platforms(self, svc, monkeypatch):
        singleton = MagicMock()
        singleton.search = AsyncMock(
            side_effect=[
                {"status": "success", "data": [1]},
                RuntimeError("slack down"),
            ]
        )
        monkeypatch.setattr(
            "integrations.universal_integration_service.universal_integration_service",
            singleton,
        )
        result = await svc.execute_tool(
            "local-tools",
            "global_search",
            {"query": "q", "platforms": ["gmail", "slack"]},
            {},
        )
        assert result["gmail"] == {"status": "success", "data": [1]}
        assert result["slack"]["status"] == "error"

    @pytest.mark.asyncio
    async def test_global_search_fallback_to_connections(self, svc, monkeypatch):
        singleton = MagicMock()
        singleton.search = AsyncMock(return_value={"status": "success"})
        monkeypatch.setattr(
            "integrations.universal_integration_service.universal_integration_service",
            singleton,
        )
        conn_service = MagicMock()
        conn_service.get_connections = MagicMock(
            return_value=[{"integration_id": "slack", "status": "active"}]
        )
        monkeypatch.setattr("core.connection_service.connection_service", conn_service)
        result = await svc.execute_tool(
            "local-tools", "global_search", {"query": "q"}, {"user_id": "u"}
        )
        assert result == {"slack": {"status": "success"}}

    @pytest.mark.asyncio
    async def test_call_integration(self, svc, monkeypatch):
        singleton = MagicMock()
        singleton.execute = AsyncMock(return_value={"status": "success"})
        monkeypatch.setattr(
            "integrations.universal_integration_service.universal_integration_service",
            singleton,
        )
        result = await svc.execute_tool(
            "local-tools",
            "call_integration",
            {"service": "hubspot", "action": "create", "params": {}},
            {},
        )
        assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_list_integrations(self, svc):
        result = await svc.execute_tool("local-tools", "list_integrations", {}, {})
        assert result["native_count"] > 0
        assert result["native_integrations"] == sorted(result["native_integrations"])


# ============================================================================
# execute_tool: WhatsApp tools
# ============================================================================


class TestExecuteToolWhatsApp:
    @pytest.fixture(autouse=True)
    def _neutralize_registry(self, monkeypatch):
        _no_registry(monkeypatch)

    @pytest.mark.asyncio
    async def test_whatsapp_send_message_import_error(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "_check_hitl_policy", AsyncMock(return_value=None))
        monkeypatch.setitem(sys.modules, "integrations.whatsapp_service_manager", None)
        result = await svc.execute_tool(
            "local-tools", "whatsapp_send_message", {"to": "+1", "message": "hi"}, {}
        )
        assert result == {"error": "WhatsApp Service modules not found."}

    @pytest.mark.asyncio
    async def test_whatsapp_send_message_unavailable(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "_check_hitl_policy", AsyncMock(return_value=None))
        manager = MagicMock()
        manager.status = "disconnected"
        manager.initialize_service = AsyncMock()
        _fake_module(
            monkeypatch, "integrations.whatsapp_service_manager", whatsapp_service_manager=manager
        )
        result = await svc.execute_tool(
            "local-tools", "whatsapp_send_message", {"to": "+1", "message": "hi"}, {}
        )
        assert "unavailable" in result["error"]

    @pytest.mark.asyncio
    async def test_whatsapp_send_message_success(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "_check_hitl_policy", AsyncMock(return_value=None))
        manager = MagicMock()
        manager.status = "connected"
        manager.integration.send_message = AsyncMock(return_value="sent")
        _fake_module(
            monkeypatch, "integrations.whatsapp_service_manager", whatsapp_service_manager=manager
        )
        result = await svc.execute_tool(
            "local-tools", "whatsapp_send_message", {"to": "+1", "message": "hi"}, {}
        )
        assert result == "sent"

    @pytest.mark.asyncio
    async def test_whatsapp_send_message_no_method(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "_check_hitl_policy", AsyncMock(return_value=None))
        manager = MagicMock()
        manager.status = "connected"
        manager.integration = MagicMock(spec=[])
        _fake_module(
            monkeypatch, "integrations.whatsapp_service_manager", whatsapp_service_manager=manager
        )
        result = await svc.execute_tool(
            "local-tools", "whatsapp_send_message", {"to": "+1", "message": "hi"}, {}
        )
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_whatsapp_send_message_exception(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "_check_hitl_policy", AsyncMock(return_value=None))
        manager = MagicMock()
        manager.status = "connected"
        manager.integration.send_message = AsyncMock(side_effect=RuntimeError("api"))
        _fake_module(
            monkeypatch, "integrations.whatsapp_service_manager", whatsapp_service_manager=manager
        )
        result = await svc.execute_tool(
            "local-tools", "whatsapp_send_message", {"to": "+1", "message": "hi"}, {}
        )
        assert "WhatsApp Send Failed" in result["error"]

    def _wa_conn(self, creds):
        conn = MagicMock()
        conn.integration_id = "whatsapp"
        conn.credentials = creds
        return conn

    @pytest.mark.asyncio
    async def test_whatsapp_send_template_no_connection(self, svc, monkeypatch):
        conn_cls = MagicMock()
        conn_cls.return_value.list_connections = AsyncMock(return_value=[])
        monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)
        result = await svc.execute_tool(
            "local-tools", "whatsapp_send_template", {}, {"user_id": "u"}
        )
        assert result == {"error": "WhatsApp Business not connected."}

    @pytest.mark.asyncio
    async def test_whatsapp_send_template_incomplete_creds(self, svc, monkeypatch):
        conn_cls = MagicMock()
        conn_cls.return_value.list_connections = AsyncMock(
            return_value=[self._wa_conn({"access_token": "a"})]
        )
        monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)
        result = await svc.execute_tool(
            "local-tools", "whatsapp_send_template", {}, {"user_id": "u"}
        )
        assert result == {"error": "WhatsApp credentials incomplete."}

    @pytest.mark.asyncio
    async def test_whatsapp_send_template_missing_args(self, svc, monkeypatch):
        conn_cls = MagicMock()
        conn_cls.return_value.list_connections = AsyncMock(
            return_value=[self._wa_conn({"access_token": "a", "phone_number_id": "p"})]
        )
        monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)
        result = await svc.execute_tool(
            "local-tools", "whatsapp_send_template", {"to": "+1"}, {"user_id": "u"}
        )
        assert result == {"error": "Both 'to' and 'template_name' are required."}

    @pytest.mark.asyncio
    async def test_whatsapp_send_template_success(self, svc, monkeypatch):
        conn_cls = MagicMock()
        conn_cls.return_value.list_connections = AsyncMock(
            return_value=[self._wa_conn({"access_token": "a", "phone_number_id": "p"})]
        )
        monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"messages": [{"id": "m1"}]}
        client = MagicMock()
        client.post = AsyncMock(return_value=resp)
        http_cls = MagicMock()
        http_cls.return_value.__aenter__ = AsyncMock(return_value=client)
        http_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr("integrations.mcp_service.httpx.AsyncClient", http_cls)
        result = await svc.execute_tool(
            "local-tools",
            "whatsapp_send_template",
            {"to": "+1", "template_name": "tpl", "language": "en", "components": []},
            {"user_id": "u"},
        )
        assert result == {"success": True, "message_id": "m1"}

    @pytest.mark.asyncio
    async def test_whatsapp_send_template_api_error(self, svc, monkeypatch):
        conn_cls = MagicMock()
        conn_cls.return_value.list_connections = AsyncMock(
            return_value=[self._wa_conn({"access_token": "a", "phone_number_id": "p"})]
        )
        monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)
        resp = MagicMock()
        resp.status_code = 400
        resp.text = "bad request"
        client = MagicMock()
        client.post = AsyncMock(return_value=resp)
        http_cls = MagicMock()
        http_cls.return_value.__aenter__ = AsyncMock(return_value=client)
        http_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr("integrations.mcp_service.httpx.AsyncClient", http_cls)
        result = await svc.execute_tool(
            "local-tools",
            "whatsapp_send_template",
            {"to": "+1", "template_name": "tpl"},
            {"user_id": "u"},
        )
        assert "WhatsApp API error: bad request" in result["error"]

    @pytest.mark.asyncio
    async def test_whatsapp_send_template_http_exception(self, svc, monkeypatch):
        conn_cls = MagicMock()
        conn_cls.return_value.list_connections = AsyncMock(
            return_value=[self._wa_conn({"access_token": "a", "phone_number_id": "p"})]
        )
        monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)
        client = MagicMock()
        client.post = AsyncMock(side_effect=RuntimeError("network"))
        http_cls = MagicMock()
        http_cls.return_value.__aenter__ = AsyncMock(return_value=client)
        http_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr("integrations.mcp_service.httpx.AsyncClient", http_cls)
        result = await svc.execute_tool(
            "local-tools",
            "whatsapp_send_template",
            {"to": "+1", "template_name": "tpl"},
            {"user_id": "u"},
        )
        assert "Failed to send WhatsApp template" in result["error"]

    @pytest.mark.asyncio
    async def test_whatsapp_list_templates_no_connection(self, svc, monkeypatch):
        conn_cls = MagicMock()
        conn_cls.return_value.list_connections = AsyncMock(return_value=[])
        monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)
        result = await svc.execute_tool(
            "local-tools", "whatsapp_list_templates", {}, {"user_id": "u"}
        )
        assert result == {"error": "WhatsApp Business not connected."}

    @pytest.mark.asyncio
    async def test_whatsapp_list_templates_success(self, svc, monkeypatch):
        conn_cls = MagicMock()
        conn_cls.return_value.list_connections = AsyncMock(
            return_value=[self._wa_conn({"access_token": "a", "waba_id": "w"})]
        )
        monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "data": [{"name": "t1", "status": "approved", "category": "marketing"}]
        }
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        http_cls = MagicMock()
        http_cls.return_value.__aenter__ = AsyncMock(return_value=client)
        http_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr("integrations.mcp_service.httpx.AsyncClient", http_cls)
        result = await svc.execute_tool(
            "local-tools", "whatsapp_list_templates", {}, {"user_id": "u"}
        )
        assert result == {"templates": [{"name": "t1", "status": "approved", "category": "marketing"}]}


# ============================================================================
# _check_hitl_policy
# ============================================================================


class TestCheckHITLPolicy:
    def _db_with(self, workspace=None, tenant=None, user=None, agent=None):
        db = MagicMock()
        queries = [
            _query_first(value=workspace),
            _query_first(value=tenant),
            _query_first(value=user),
            _query_first(value=agent),
        ]
        db.query.side_effect = queries
        return db

    def _patch_db(self, monkeypatch, db):
        monkeypatch.setattr("core.database.SessionLocal", _session_factory(db))

    def _patch_intervention(self, monkeypatch, result=None):
        intervention = MagicMock()
        intervention.request_intervention = AsyncMock(return_value=result or {"paused": True})
        monkeypatch.setattr("core.intervention_service.intervention_service", intervention)
        return intervention

    @pytest.mark.asyncio
    async def test_no_require_hitl(self, svc, monkeypatch):
        tenant = MagicMock()
        tenant.metadata_json = {"governance": {"require_hitl_external": False}}
        workspace = MagicMock()
        workspace.tenant_id = "t1"
        self._patch_db(monkeypatch, self._db_with(workspace=workspace, tenant=tenant))
        result = await svc._check_hitl_policy("ws1", "send_email", {"to": "x"})
        assert result is None

    @pytest.mark.asyncio
    async def test_risky_tool_intercepts(self, svc, monkeypatch):
        tenant = MagicMock()
        tenant.metadata_json = {"governance": {"require_hitl_external": True}}
        workspace = MagicMock()
        workspace.tenant_id = "t1"
        self._patch_db(monkeypatch, self._db_with(workspace=workspace, tenant=tenant))
        intervention = self._patch_intervention(monkeypatch, {"paused": True})
        result = await svc._check_hitl_policy(
            "ws1", "send_email", {"to": "x@y"}, {"agent_id": "a1", "user_id": "u1"}
        )
        assert result == {"paused": True}
        intervention.request_intervention.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_autonomous_agent_auto_approved(self, svc, monkeypatch):
        tenant = MagicMock()
        tenant.metadata_json = {
            "governance": {
                "require_hitl_external": True,
                "allow_autonomous_external": True,
            }
        }
        workspace = MagicMock()
        workspace.tenant_id = "t1"
        agent = MagicMock()
        agent.maturity_level = 5
        agent.status = "autonomous"  # R81e: tier-name comparison
        agent.name = "Auto"
        self._patch_db(
            monkeypatch, self._db_with(workspace=workspace, tenant=tenant, agent=agent)
        )
        result = await svc._check_hitl_policy(
            "ws1", "whatsapp_send_message", {"to": "+1"}, {"agent_id": "a1", "user_id": "u1"}
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_user_force_hitl_overrides_autonomous(self, svc, monkeypatch):
        tenant = MagicMock()
        tenant.metadata_json = {
            "governance": {
                "require_hitl_external": True,
                "allow_autonomous_external": True,
            }
        }
        workspace = MagicMock()
        workspace.tenant_id = "t1"
        user = MagicMock()
        user.notification_preferences = {"force_agent_approval": True}
        agent = MagicMock()
        agent.maturity_level = 5
        agent.status = "autonomous"  # R81e: tier-name comparison
        agent.name = "Auto"
        self._patch_db(
            monkeypatch,
            self._db_with(workspace=workspace, tenant=tenant, user=user, agent=agent),
        )
        intervention = self._patch_intervention(monkeypatch, {"paused": True})
        result = await svc._check_hitl_policy(
            "ws1", "send_message", {"target": "t"}, {"agent_id": "a1", "user_id": "u1"}
        )
        assert result == {"paused": True}

    @pytest.mark.asyncio
    async def test_required_role_added_to_reason(self, svc, monkeypatch):
        tenant = MagicMock()
        tenant.metadata_json = {
            "governance": {
                "require_hitl_external": True,
                "roles": {"send_message": "finance_lead"},
            }
        }
        workspace = MagicMock()
        workspace.tenant_id = "t1"
        self._patch_db(monkeypatch, self._db_with(workspace=workspace, tenant=tenant))
        intervention = self._patch_intervention(monkeypatch, {"paused": True})
        await svc._check_hitl_policy(
            "ws1", "send_message", {"target": "t"}, {"user_id": "u1"}
        )
        assert "finance_lead" in intervention.request_intervention.await_args.kwargs["reason"]

    @pytest.mark.asyncio
    async def test_non_risky_tool_not_intercepted(self, svc, monkeypatch):
        tenant = MagicMock()
        tenant.metadata_json = {"governance": {"require_hitl_external": True}}
        workspace = MagicMock()
        workspace.tenant_id = "t1"
        self._patch_db(monkeypatch, self._db_with(workspace=workspace, tenant=tenant))
        result = await svc._check_hitl_policy("ws1", "canvas_render", {}, {})
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_workspace_returns_none(self, svc, monkeypatch):
        # R81b: fail-closed — a missing workspace BLOCKS risky tools.
        self._patch_db(monkeypatch, self._db_with(workspace=None))
        result = await svc._check_hitl_policy("ghost", "send_email", {}, {})
        assert result and result.get("blocked_by") == "hitl_policy_error"

    @pytest.mark.asyncio
    async def test_missing_tenant_returns_none(self, svc, monkeypatch):
        # R81b: fail-closed — a missing tenant BLOCKS risky tools.
        workspace = MagicMock()
        workspace.tenant_id = "t1"
        self._patch_db(monkeypatch, self._db_with(workspace=workspace, tenant=None))
        result = await svc._check_hitl_policy("ws1", "send_email", {}, {})
        assert result and result.get("blocked_by") == "hitl_policy_error"

    @pytest.mark.asyncio
    async def test_no_user_and_no_agent_intercepts(self, svc, monkeypatch):
        tenant = MagicMock()
        tenant.metadata_json = {"governance": {"require_hitl_external": True}}
        workspace = MagicMock()
        workspace.tenant_id = "t1"
        self._patch_db(monkeypatch, self._db_with(workspace=workspace, tenant=tenant))
        self._patch_intervention(monkeypatch, {"paused": True})
        result = await svc._check_hitl_policy("ws1", "whatsapp_send_template", {}, {})
        assert result == {"paused": True}


# ============================================================================
# execute_entity_tool + entity helpers
# ============================================================================


class TestExecuteEntityTool:
    @pytest.mark.asyncio
    async def test_success(self, svc, monkeypatch):
        monkeypatch.setattr(
            svc, "execute_tool", AsyncMock(return_value={"done": True})
        )
        result = await svc.execute_entity_tool(
            {
                "entity_id": "e1",
                "entity_type_slug": "vendor",
                "tenant_id": "t1",
                "agent_id": "a1",
                "entity_data": {"email": "x@y.z"},
                "workspace_id": "w1",
            },
            "send_email",
            {"to": "entity.email"},
        )
        assert result["status"] == "success"
        assert result["entity_id"] == "e1"
        assert result["entity_type"] == "vendor"
        assert result["result"] == {"done": True}

    @pytest.mark.asyncio
    async def test_missing_required_field(self, svc):
        result = await svc.execute_entity_tool(
            {"entity_type_slug": "vendor", "tenant_id": "t"}, "send_email", {}
        )
        assert result["status"] == "error"
        assert "missing" in result["error"]

    @pytest.mark.asyncio
    async def test_execution_error(self, svc, monkeypatch):
        monkeypatch.setattr(
            svc, "execute_tool", AsyncMock(side_effect=RuntimeError("boom"))
        )
        result = await svc.execute_entity_tool(
            {
                "entity_id": "e1",
                "entity_type_slug": "vendor",
                "tenant_id": "t1",
                "agent_id": "a1",
            },
            "send_email",
            {},
        )
        assert result["status"] == "error"
        assert "boom" in result["error"]


class TestEntityHelpers:
    def test_inject_entity_context(self, svc):
        class Ctx:
            entity_data = {"properties": {"email": "x@y"}, "name": "Acme"}

        aug = svc._inject_entity_context(
            {"to": "entity.properties.email", "subject": "Hi", "cc": None},
            Ctx(),
        )
        assert aug["to"] == "x@y"
        assert aug["subject"] == "Hi"
        assert aug["cc"] is None

    def test_get_nested_field(self, svc):
        data = {"a": {"b": {"c": 42}}}
        assert svc._get_nested_field(data, "a.b.c") == 42
        assert svc._get_nested_field(data, "a.missing") is None
        assert svc._get_nested_field(data, "a.b.c.d") is None
        assert svc._get_nested_field("not-a-dict", "x") is None


# ============================================================================
# check_entity_skill_permission
# ============================================================================


class TestCheckEntitySkillPermission:
    @pytest.mark.asyncio
    async def test_cache_hit(self, svc):
        import time

        svc._permission_cache = {
            "entity_skill_perm:t1:vendor:s1": (time.time(), {"allowed": True})
        }
        result = svc.check_entity_skill_permission("t1", "vendor", "s1")
        assert result == {"allowed": True}

    @pytest.mark.asyncio
    async def test_cache_miss_populates(self, svc, monkeypatch):
        skill_service = MagicMock()
        skill_service.check_skill_permission = MagicMock(
            return_value={"allowed": True, "reason": "ok"}
        )
        monkeypatch.setattr(
            "core.entity_skill_service.get_entity_skill_service", lambda: skill_service
        )
        db = MagicMock()
        skill = MagicMock()
        skill.name = "Send Email"
        db.query.return_value.filter.return_value.first.return_value = skill
        monkeypatch.setattr("core.database.SessionLocal", _session_factory(db))
        result = svc.check_entity_skill_permission("t1", "vendor", "s1")
        assert result == {"allowed": True, "reason": "ok", "skill_name": "Send Email"}
        assert "entity_skill_perm:t1:vendor:s1" in svc._permission_cache
        second = svc.check_entity_skill_permission("t1", "vendor", "s1")
        assert second["skill_name"] == "Send Email"

    @pytest.mark.asyncio
    async def test_permission_service_exception(self, svc, monkeypatch):
        def _boom(*a, **k):
            raise RuntimeError("no service")

        monkeypatch.setattr("core.entity_skill_service.get_entity_skill_service", _boom)
        result = svc.check_entity_skill_permission("t1", "vendor", "s1")
        assert result["allowed"] is False
        assert "Permission check failed" in result["reason"]


# ============================================================================
# web_search
# ============================================================================


class TestWebSearch:
    def _http_cls(self, post_result=None, post_raises=None):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"results": [{"title": "r1"}]}
        if post_result is not None:
            resp = post_result
        client = MagicMock()
        if post_raises is not None:
            client.post = AsyncMock(side_effect=post_raises)
        else:
            client.post = AsyncMock(return_value=resp)
        http_cls = MagicMock()
        http_cls.return_value.__aenter__ = AsyncMock(return_value=client)
        http_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        return http_cls

    @pytest.mark.asyncio
    async def test_env_key_success(self, svc, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "env-key")
        monkeypatch.setattr("integrations.mcp_service.httpx.AsyncClient", self._http_cls())
        result = await svc.web_search("what is atom")
        assert result["results"] == [{"title": "r1"}]

    @pytest.mark.asyncio
    async def test_byok_key_priority(self, svc, monkeypatch):
        manager = MagicMock()
        manager.get_tenant_api_key = MagicMock(return_value="byok-key")
        monkeypatch.setattr("integrations.mcp_service.get_byok_manager", lambda: manager)
        db = MagicMock()
        monkeypatch.setattr("integrations.mcp_service.SessionLocal", _session_factory(db))
        monkeypatch.setattr("integrations.mcp_service.httpx.AsyncClient", self._http_cls())
        result = await svc.web_search("q", tenant_id="t1")
        assert result["results"] == [{"title": "r1"}]
        manager.get_tenant_api_key.assert_called_once()

    @pytest.mark.asyncio
    async def test_byok_key_lookup_error_falls_back(self, svc, monkeypatch):
        def _boom(*a, **k):
            raise RuntimeError("db")

        manager = MagicMock()
        manager.get_tenant_api_key = _boom
        monkeypatch.setattr("integrations.mcp_service.get_byok_manager", lambda: manager)
        monkeypatch.setenv("TAVILY_API_KEY", "env-key")
        monkeypatch.setattr("integrations.mcp_service.httpx.AsyncClient", self._http_cls())
        result = await svc.web_search("q", tenant_id="t1")
        assert result["results"] == [{"title": "r1"}]

    @pytest.mark.asyncio
    async def test_no_key_returns_error(self, svc, monkeypatch):
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        result = await svc.web_search("q")
        assert result["results"] == []
        assert "not configured" in result["error"]

    @pytest.mark.asyncio
    async def test_non_200_returns_error(self, svc, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "env-key")
        resp = MagicMock()
        resp.status_code = 500
        monkeypatch.setattr(
            "integrations.mcp_service.httpx.AsyncClient", self._http_cls(post_result=resp)
        )
        result = await svc.web_search("q")
        assert result["results"] == []
        assert "not configured" in result["error"]

    @pytest.mark.asyncio
    async def test_http_exception_returns_error(self, svc, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "env-key")
        monkeypatch.setattr(
            "integrations.mcp_service.httpx.AsyncClient",
            self._http_cls(post_raises=RuntimeError("timeout")),
        )
        result = await svc.web_search("q")
        assert result["results"] == []
        assert "not configured" in result["error"]


# ============================================================================
# Remaining edge branches
# ============================================================================


class TestRemainingEdges:
    @pytest.mark.asyncio
    async def test_whatsapp_list_templates_incomplete_creds(self, svc, monkeypatch):
        conn_cls = MagicMock()
        conn = MagicMock()
        conn.integration_id = "whatsapp"
        conn.credentials = {"access_token": "a"}
        conn_cls.return_value.list_connections = AsyncMock(return_value=[conn])
        monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)
        result = await svc.execute_tool(
            "local-tools", "whatsapp_list_templates", {}, {"user_id": "u"}
        )
        assert result == {"error": "WhatsApp credentials incomplete."}

    @pytest.mark.asyncio
    async def test_whatsapp_list_templates_api_error(self, svc, monkeypatch):
        conn_cls = MagicMock()
        conn = MagicMock()
        conn.integration_id = "whatsapp"
        conn.credentials = {"access_token": "a", "waba_id": "w"}
        conn_cls.return_value.list_connections = AsyncMock(return_value=[conn])
        monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)
        resp = MagicMock()
        resp.status_code = 401
        resp.text = "unauthorized"
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        http_cls = MagicMock()
        http_cls.return_value.__aenter__ = AsyncMock(return_value=client)
        http_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr("integrations.mcp_service.httpx.AsyncClient", http_cls)
        result = await svc.execute_tool(
            "local-tools", "whatsapp_list_templates", {}, {"user_id": "u"}
        )
        assert "WhatsApp API error: unauthorized" in result["error"]

    @pytest.mark.asyncio
    async def test_whatsapp_send_message_initializes_service(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "_check_hitl_policy", AsyncMock(return_value=None))
        manager = MagicMock()
        manager.status = "initializing"
        manager.initialize_service = AsyncMock(side_effect=lambda: setattr(manager, "status", "connected"))
        manager.integration.send_message = AsyncMock(return_value="sent")
        _fake_module(
            monkeypatch, "integrations.whatsapp_service_manager", whatsapp_service_manager=manager
        )
        result = await svc.execute_tool(
            "local-tools", "whatsapp_send_message", {"to": "+1", "message": "hi"}, {}
        )
        assert result == "sent"
        manager.initialize_service.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_external_hub_skips_brightdata(self, svc, monkeypatch):
        hub = MagicMock()
        hub.tools_cache = {"brightdata": [SimpleNamespace(name="scrape_tool")]}
        hub.call_external_tool = AsyncMock(return_value="external")
        monkeypatch.setattr("core.mcp_service.mcp_service", hub)
        monkeypatch.setattr(
            "core.action_registry.action_registry.get_action", lambda n: None
        )
        monkeypatch.setattr(
            "core.action_registry.action_registry.execute_action",
            AsyncMock(side_effect=KeyError("unused")),
        )
        monkeypatch.setattr(svc, "execute_tool", AsyncMock(return_value="local"))
        result = await svc.call_tool("scrape_tool", {})
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_cloud_access_check_exception_fails_closed(self, svc, monkeypatch):
        _no_registry(monkeypatch)

        def _boom(*a, **k):
            raise RuntimeError("db down")

        monkeypatch.setattr("core.database.SessionLocal", _boom)
        result = await svc.call_tool("browser_navigate", {"url": "http://x"}, {"computer_use_mode": "cloud", "workspace_id": "ws-9"})
        assert "Enterprise" in result

    @pytest.mark.asyncio
    async def test_list_workflows_parses_json(self, svc, monkeypatch, tmp_path):
        state_dir = tmp_path / "workflow_states"
        state_dir.mkdir()
        (state_dir / "wf.json").write_text(
            '{"workflow_id": "w1", "name": "N", "description": "D", "trigger": "schedule"}'
        )
        (state_dir / "broken.json").write_text("{not json")
        monkeypatch.setattr("integrations.mcp_service.os.path.exists", lambda p: True)
        monkeypatch.setattr("integrations.mcp_service.os.listdir", lambda p: ["wf.json", "broken.json"])

        real_open = open

        def _open(path, *args, **kwargs):
            return real_open(state_dir / os.path.basename(path), *args, **kwargs)

        monkeypatch.setattr("builtins.open", _open)
        result = await svc.execute_tool("local-tools", "list_workflows", {}, {})
        assert result == [
            {
                "id": "w1",
                "name": "N",
                "description": "D",
                "trigger": "schedule",
            }
        ]

    @pytest.mark.asyncio
    async def test_get_inventory_levels_shopify_connection(self, svc, monkeypatch):
        conn = MagicMock()
        conn.piece_name = "shopify"
        conn.credentials = {"access_token": "t"}
        conn.metadata = {"shop_url": "s.myshopify.com"}
        conn_cls = MagicMock()
        conn_cls.return_value.list_connections = AsyncMock(return_value=[conn])
        monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)
        shopify = MagicMock()
        shopify.get_inventory_levels = AsyncMock(return_value=[{"id": 1}])
        monkeypatch.setattr("integrations.shopify_service.ShopifyService", lambda **kw: shopify)
        result = await svc.execute_tool(
            "local-tools", "get_inventory_levels", {}, {"user_id": "u"}
        )
        assert result == [{"id": 1}]
