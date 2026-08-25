"""Coverage wave W85 — integrations/mcp_service.py to >=80% statement coverage.

Conventions (W75B/W78B/W79C): plain pytest + unittest.mock, patched at real
module boundaries (source-module attributes for lazy imports), zero network /
LLM spend / real DB. asyncio_mode=auto (pytest.ini) so bare async tests work.
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

import integrations.mcp_service as mcp_mod
from integrations.mcp_service import MCPService


# ============================================================================
# Helpers
# ============================================================================
def mk_session(first=None, all_=None):
    """Build a SessionLocal factory usable as `with SessionLocal() as db:`."""
    db = MagicMock(name="db")
    q = db.query.return_value
    q.filter.return_value.first.return_value = first
    q.filter.return_value.all.return_value = all_ or []
    q.first.return_value = first
    q.all.return_value = all_ or []
    cm = MagicMock(name="sess_cm")
    cm.__enter__.return_value = db
    cm.__exit__.return_value = False
    factory = MagicMock(name="SessionLocal", return_value=cm)
    factory.db = db
    return factory


def fake_httpx_client(post_resp=None, get_resp=None, exc=None):
    client = MagicMock(name="http_client")
    client.post = AsyncMock(return_value=post_resp)
    client.get = AsyncMock(return_value=get_resp)
    if exc:
        client.post = AsyncMock(side_effect=exc)
        client.get = AsyncMock(side_effect=exc)
    cm = MagicMock(name="http_cm")
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(name="AsyncClient", return_value=cm)


def http_response(status=200, payload=None, text=""):
    return MagicMock(
        status_code=status,
        json=Mock(return_value=payload or {}),
        text=text,
    )


@pytest.fixture
def svc(monkeypatch):
    """Fresh MCPService (bypass singleton) with gates neutralized."""
    monkeypatch.setattr(MCPService, "_instance", None)
    s = MCPService()
    s.active_servers = {}
    s.tenant_id = "default"
    return s


@pytest.fixture(autouse=True)
def base_env(monkeypatch, tmp_path):
    # Neutral gates (overridden per-test when the gate IS the subject)
    monkeypatch.setattr(
        "core.sandbox_gate.evaluate_tool_call", lambda *a, **k: None
    )
    # No external-agent resolution -> unrestricted
    monkeypatch.setattr(
        "core.capability_resolver.get_agent_for_context", lambda ctx: None
    )
    # Default DB sessions return nothing
    sess = mk_session()
    monkeypatch.setattr(mcp_mod, "SessionLocal", sess)
    monkeypatch.setattr("core.database.SessionLocal", sess)
    # Empty core tool registry
    reg = MagicMock(name="tool_registry")
    reg.get.return_value = None
    reg.get_function.return_value = None
    reg.get_simplified_tools.return_value = []
    monkeypatch.setattr(mcp_mod, "get_tool_registry", lambda: reg)
    # Keep list_workflows away from any real workflow_states dir
    monkeypatch.chdir(tmp_path)
    return monkeypatch


# ============================================================================
# Construction / capabilities / health / execute_operation
# ============================================================================
def test_singleton_and_capabilities(svc):
    again = MCPService()
    assert again is svc
    caps = svc.get_capabilities()
    assert caps["supports_webhooks"] is False
    assert any(op["id"] == "call_tool" for op in caps["operations"])


def test_health_check(svc):
    h = svc.health_check()
    assert h["ok"] is True and h["service"] == "mcp"


async def test_execute_operation_dispatch(svc):
    svc.get_openai_tools = AsyncMock(return_value=[{"name": "t"}])
    svc.get_server_tools = AsyncMock(return_value=[{"name": "t"}])
    svc.call_tool = AsyncMock(return_value={"ok": 1})
    svc.search_tools = AsyncMock(return_value=[{"name": "t"}])
    svc.web_search = AsyncMock(return_value={"results": []})

    assert (await svc.execute_operation("get_openai_tools", {}))["success"]
    assert (await svc.execute_operation(
        "get_server_tools", {"server_id": "x"}))["success"]
    assert (await svc.execute_operation(
        "call_tool", {"tool_name": "t", "arguments": {"a": 1}}))["success"]
    assert (await svc.execute_operation(
        "search_tools", {"query": "q"}))["success"]
    assert (await svc.execute_operation(
        "web_search", {"query": "q"}, {"tenant_id": "t1"}))["success"]
    bad = await svc.execute_operation("bogus", {})
    assert bad["success"] is False and "Unknown operation" in bad["error"]
    # exception branch
    svc.call_tool = AsyncMock(side_effect=RuntimeError("boom"))
    err = await svc.execute_operation("call_tool", {"tool_name": "t"})
    assert err == {"success": False, "error": "boom"}


# ============================================================================
# Tool listing
# ============================================================================
async def test_get_server_tools_pseudo_servers(svc):
    g = await svc.get_server_tools("google-search")
    assert any(t["name"] == "web_search" for t in g)
    local = await svc.get_server_tools("local-tools")
    assert len(local) > 30
    svc.active_servers["dyn"] = {"tools": [{"name": "d1"}]}
    assert await svc.get_server_tools("dyn") == [{"name": "d1"}]
    assert await svc.get_server_tools("nope") == []


async def test_get_all_tools_and_openai(svc, base_env):
    import core.action_registry as ar_mod
    base_env.setattr(
        ar_mod.action_registry, "get_all_definitions",
        lambda: [SimpleNamespace(
            name="act1", description="d",
            parameters_schema={"properties": {"a": {"type": "string"},
                                              "b": {"type": "int"}},
                               "required": ["a"]})],
    )
    svc.active_servers["ext"] = {"tools": [{"name": "ext_tool",
                                            "description": "x",
                                            "parameters": {}}]}
    tools = await svc.get_all_tools()
    names = [t["name"] for t in tools]
    assert "act1" in names and "ext_tool" in names
    # local tool not present in registry gets surfaced, registry one deduped
    assert "global_search" in names
    oai = await svc.get_openai_tools()
    assert isinstance(oai, list)


async def test_search_tools(svc):
    svc.get_all_tools = AsyncMock(return_value=[
        {"name": "search_files", "description": "find files"},
        {"name": "files_index", "description": "search inside files"},
        {"name": "other", "description": "nothing"},
    ])
    res = await svc.search_tools("search", limit=2)
    assert res[0]["name"] == "search_files"
    assert len(res) == 2
    assert await svc.search_tools("zzz") == []


async def test_get_active_connections(svc):
    svc.active_servers = {"s1": {"name": "S1", "connected_at": "now"}}
    conns = await svc.get_active_connections()
    assert conns[0]["server_id"] == "s1" and conns[0]["status"] == "connected"


# ============================================================================
# register_integration_tools
# ============================================================================
async def test_register_integration_tools(svc, base_env):
    good = MagicMock()
    good.get_operations.return_value = [
        {"name": "op1", "description": "d", "parameters": {}, "complexity": 3}
    ]
    no_service = None
    no_ops = MagicMock(spec=[])  # no get_operations
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [
        SimpleNamespace(connector_id="good"),
        SimpleNamespace(connector_id="missing"),
        SimpleNamespace(connector_id="noops"),
        SimpleNamespace(connector_id="bad"),
    ]
    registry = MagicMock()

    async def get_service_instance(cid, tid):
        if cid == "bad":
            raise RuntimeError("x")
        return {"good": good, "missing": no_service, "noops": no_ops}[cid]
    registry.get_service_instance = get_service_instance
    base_env.setattr("core.integration_registry.IntegrationRegistry",
                     lambda db=None, use_cache=False: registry)
    tools = await svc.register_integration_tools("t1", db=db)
    assert len(tools) == 1 and tools[0]["name"] == "good_op1"
    assert svc.tools_cache["t1:good:op1"]["operation_name"] == "op1"
    # db=None branch creates (and closes) its own session
    base_env.setattr(mcp_mod, "SessionLocal", mk_session())
    assert await svc.register_integration_tools("t1") == []


# ============================================================================
# execute_integration_tool
# ============================================================================
async def test_execute_integration_tool(svc, base_env):
    r1 = await svc.execute_integration_tool("nounderscore", {}, {})
    assert r1["status"] == "error"
    r2 = await svc.execute_integration_tool("conn_op", {}, {"agent_id": "a"})
    assert "tenant_id" in r2["error"]
    r3 = await svc.execute_integration_tool("conn_op", {}, {})
    assert "tenant_id" in r3["error"]
    inst = MagicMock()
    inst.execute = AsyncMock(return_value={"status": "success"})
    base_env.setattr(
        "integrations.universal_integration_service.UniversalIntegrationService",
        lambda: inst)
    ok = await svc.execute_integration_tool(
        "conn_op", {"x": 1}, {"tenant_id": "t", "agent_id": "a"})
    assert ok == {"status": "success"}
    inst.execute = AsyncMock(side_effect=RuntimeError("boom"))
    err = await svc.execute_integration_tool(
        "conn_op", {}, {"tenant_id": "t", "agent_id": "a"})
    assert err["status"] == "error"


# ============================================================================
# call_tool gates & dispatch
# ============================================================================
async def test_call_tool_capability_gate_blocks(svc, base_env):
    agent = SimpleNamespace(id="a1", capabilities=["search_files"],
                            status="autonomous")
    base_env.setattr(
        "core.capability_resolver.get_agent_for_context", lambda ctx: agent)
    res = await svc.call_tool("delete_everything", {}, {"agent_id": "a1"})
    assert res["success"] is False and res["blocked_by"] == "capability_gate"


async def test_call_tool_capability_gate_exception_fails_open(svc, base_env):
    base_env.setattr(
        "core.capability_resolver.get_agent_for_context",
        Mock(side_effect=RuntimeError("db down")))
    svc.execute_tool = AsyncMock(return_value="ran")
    assert await svc.call_tool("search_contacts", {}, {}) == "ran"


async def test_call_tool_sandbox_enforced_and_shadow(svc, base_env):
    base_env.setattr(
        "core.sandbox_gate.evaluate_tool_call",
        lambda *a, **k: SimpleNamespace(
            requires_review=True, enforced=True, decision="blocked",
            violation_detail="no network", violation_type="egress"))
    res = await svc.call_tool("anything", {}, {"agent_id": "a"})
    assert res == "Sandbox blocked: no network"
    base_env.setattr(
        "core.sandbox_gate.evaluate_tool_call",
        lambda *a, **k: SimpleNamespace(
            requires_review=True, enforced=False, decision="flagged",
            violation_detail="d", violation_type="t"))
    # shadow mode proceeds (tool not found => dispatch continued past gate)
    assert "not found" in (await svc.call_tool("anything", {},
                                               {"agent_id": "a"}))["error"]
    # gate raising fails open (defensive branch via real raise)
    base_env.setattr(
        "core.sandbox_gate.evaluate_tool_call",
        Mock(side_effect=RuntimeError("gate broken")))
    assert "not found" in (await svc.call_tool("anything", {}))["error"]


async def test_call_tool_entity_bound(svc, base_env):
    svc.execute_entity_tool = AsyncMock(return_value={"status": "success"})
    res = await svc.call_tool("search_files", {},
                              {"entity_id": "e1", "entity_type_slug": "vendor",
                               "tenant_id": "t"})
    svc.execute_entity_tool.assert_awaited_once()
    assert res["status"] == "success"


async def test_call_tool_action_registry(svc, base_env):
    import core.action_registry as ar_mod
    base_env.setattr(ar_mod.action_registry, "get_action",
                     lambda n: object() if n == "documents.search" else None)
    base_env.setattr(ar_mod.action_registry, "execute_action",
                     AsyncMock(return_value={"done": True}))
    res = await svc.call_tool("documents.search", {"q": "x"})
    assert res == {"done": True}


async def test_call_tool_hardcoded_and_dynamic_servers(svc, base_env):
    svc.execute_tool = AsyncMock(return_value="ok")
    assert await svc.call_tool("search_contacts", {}) == "ok"
    svc.active_servers["dyn"] = {"tools": [{"name": "dyn_tool"}]}
    assert await svc.call_tool("dyn_tool", {}) == "ok"


async def test_call_tool_external_hub(svc, base_env):
    hub = SimpleNamespace(
        tools_cache={"srv": [SimpleNamespace(name="hub_tool")]},
        call_external_tool=AsyncMock(return_value="hub-ok"))
    base_env.setattr("core.mcp_service.mcp_service", hub)
    assert await svc.call_tool("hub_tool", {}) == "hub-ok"
    # hub raising is tolerated
    hub.call_external_tool = AsyncMock(side_effect=RuntimeError("x"))
    res = await svc.call_tool("hub_tool", {})
    assert "not found" in res["error"]


async def test_call_tool_not_found(svc, base_env):
    res = await svc.call_tool("no_such_tool_anywhere", {})
    assert "not found on any active server" in res["error"]


# ============================================================================
# execute_tool: registry path
# ============================================================================
async def test_execute_tool_registry_sync_and_async(svc, base_env):
    reg = MagicMock()
    sync_fn = MagicMock(return_value="sync-result")
    async def async_fn(**kw): return "async-result"
    reg.get.side_effect = lambda n: {"sync_tool": object(),
                                     "async_tool": object()}.get(n)
    reg.get_function.side_effect = lambda n: {"sync_tool": sync_fn,
                                              "async_tool": async_fn}[n]
    base_env.setattr(mcp_mod, "get_tool_registry", lambda: reg)
    assert await svc.execute_tool("local-tools", "sync_tool",
                                  {"a": 1}, {"ctx_key": "v"}) == "sync-result"
    # MagicMock accepts **kwargs, so context keys flow through var-kw
    assert sync_fn.call_args.kwargs["a"] == 1
    assert await svc.execute_tool("google-search", "async_tool", {}) == "async-result"
    # registered-but-no-function -> ValueError
    reg.get.side_effect = None
    reg.get_function.side_effect = None
    reg.get.return_value = object()
    reg.get_function.return_value = None
    with pytest.raises(ValueError):
        await svc.execute_tool("local-tools", "ghost_tool", {})


async def test_execute_tool_var_kw_context_forward(svc, base_env):
    reg = MagicMock()
    def tool_fn(**kw): return kw
    reg.get.return_value = object()
    reg.get_function.return_value = tool_fn
    base_env.setattr(mcp_mod, "get_tool_registry", lambda: reg)
    out = await svc.execute_tool("local-tools", "t", {"a": 1},
                                 {"agent_id": "ag"})
    assert out == {"a": 1, "agent_id": "ag"}


async def test_execute_tool_untyped_signature_fails_safe(svc, base_env):
    reg = MagicMock()
    def tool_fn(a): return a
    reg.get.return_value = object()
    reg.get_function.return_value = tool_fn
    base_env.setattr(mcp_mod, "get_tool_registry", lambda: reg)
    # inspect.signature raises TypeError -> kwargs stay just the arguments
    with patch("integrations.mcp_service.inspect.signature",
               side_effect=TypeError):
        assert await svc.execute_tool("local-tools", "t", {"a": 5}) == 5


# ============================================================================
# execute_tool local-tools branches: DB-backed internal tools
# ============================================================================
async def test_local_finance_close_check(svc, base_env):
    agent = MagicMock()
    agent.run_close_check = AsyncMock(return_value={"status": "done"})
    base_env.setattr("accounting.close_agent.CloseChecklistAgent",
                     lambda db: agent)
    assert (await svc.execute_tool("local-tools", "finance_close_check",
                                   {"period": "2026-01"}))["status"] == "done"


async def test_local_b2b_tools(svc, base_env):
    ps = MagicMock()
    ps.extract_po_from_text = AsyncMock(return_value={"po": 1})
    ps.create_draft_order_from_po = AsyncMock(return_value={"order": 1})
    # real module currently fails to import (broken hubspot_service import),
    # so substitute a fake module
    base_env.setitem(sys.modules, "ecommerce.b2b_procurement_service",
                     SimpleNamespace(B2BProcurementService=lambda db: ps))
    push = MagicMock()
    push.push_draft_order = AsyncMock(return_value={"pushed": True})
    base_env.setitem(sys.modules, "ecommerce.b2b_data_push_service",
                     SimpleNamespace(B2BDataPushService=lambda db: push))
    assert await svc.execute_tool("local-tools", "b2b_extract_po",
                                  {"text": "PO..."}) == {"po": 1}
    assert await svc.execute_tool("local-tools", "b2b_create_draft_order",
                                  {"po_data": {}}) == {"order": 1}
    assert await svc.execute_tool("local-tools", "b2b_push_to_integrations",
                                  {"order_id": "o1"}) == {"pushed": True}


async def test_local_request_human_intervention(svc, base_env):
    from core.intervention_service import intervention_service
    with patch.object(intervention_service, "request_intervention",
                      AsyncMock(return_value={"paused": True})) as ri:
        res = await svc.execute_tool("local-tools", "request_human_intervention",
                                     {"action": "send", "reason": "why",
                                      "params": {"x": 1}}, {"workspace_id": "w"})
        assert res == {"paused": True}
        ri.assert_awaited_once()


async def test_local_trigger_workflow(svc, base_env):
    orch = MagicMock()
    orch.execute_workflow = AsyncMock(return_value=SimpleNamespace(
        status=SimpleNamespace(value="completed"), workflow_id="wf",
        results={"r": 1}, error_message=None))
    base_env.setattr("advanced_workflow_orchestrator.get_orchestrator",
                     lambda: orch)
    base_env.setattr("core.workflow_security.resolve_orchestrator_steps",
                     lambda o, wid: [SimpleNamespace()])
    base_env.setattr("core.workflow_security.has_critical_step",
                     lambda steps: False)
    res = await svc.execute_tool("local-tools", "trigger_workflow",
                                 {"workflow_id": "wf", "input_data": {}})
    assert res["status"] == "completed"
    # missing id
    assert (await svc.execute_tool("local-tools", "trigger_workflow", {})
            )["error"] == "workflow_id is required"
    # critical step refused
    base_env.setattr("core.workflow_security.has_critical_step",
                     lambda steps: True)
    assert "refused" in (await svc.execute_tool(
        "local-tools", "trigger_workflow", {"workflow_id": "wf"}))["error"]
    # unresolvable definition refused
    base_env.setattr("core.workflow_security.resolve_orchestrator_steps",
                     lambda o, wid: None)
    assert "refused" in (await svc.execute_tool(
        "local-tools", "trigger_workflow", {"workflow_id": "wf"}))["error"]


async def test_local_marketing_automation(svc, base_env):
    mkt = MagicMock()
    mkt.trigger_review_request = AsyncMock(return_value="review")
    base_env.setattr("core.marketing_agent.MarketingAgent",
                     lambda db_session=None: mkt)
    assert await svc.execute_tool("local-tools", "marketing_review_request",
                                  {"customer_id": "c"}) == "review"
    ci = MagicMock()
    ci.track_competitor_pricing = AsyncMock(return_value="pricing")
    base_env.setattr(
        "operations.automations.competitive_intel.CompetitiveIntelWorkflow",
        lambda: ci)
    assert await svc.execute_tool("local-tools", "track_competitor_pricing",
                                  {"competitors": ["a"]}) == "pricing"
    inv = MagicMock()
    inv.reconcile_inventory = AsyncMock(return_value="inv")
    base_env.setattr(
        "operations.automations.inventory_reconcile."
        "InventoryReconciliationWorkflow", lambda: inv)
    assert await svc.execute_tool("local-tools", "reconcile_inventory",
                                  {}) == "inv"
    pay = MagicMock()
    pay.reconcile_payroll = AsyncMock(return_value="pay")
    base_env.setattr(
        "finance.automations.payroll_guardian.PayrollReconciliationWorkflow",
        lambda: pay)
    assert await svc.execute_tool("local-tools", "reconcile_payroll",
                                  {"period": "2026-01"}) == "pay"


async def test_local_canvas_tool(svc, base_env):
    mgr = MagicMock()
    mgr.broadcast_event = AsyncMock(return_value=None)
    base_env.setattr("core.websockets.get_connection_manager", lambda: mgr)
    res = await svc.execute_tool("local-tools", "canvas_tool",
                                 {"action": "present", "component": "chart"},
                                 {"workspace_id": "w", "agent_id": "ag"})
    assert "Canvas update" in res
    mgr.broadcast_event.assert_awaited_once()


async def test_local_collaboration_tools_import_missing(svc):
    for tool, word in [("analyze_message", "analyze_message"),
                       ("draft_response", "draft_response"),
                       ("approve_draft", "approve_draft")]:
        res = await svc.execute_tool("local-tools", tool,
                                     {"message_id": "m", "content": "c"})
        assert res["status"] == "error" and word in res["error"]


async def test_local_ingest_message_attachment(svc):
    res = await svc.execute_tool("local-tools", "ingest_message_attachment",
                                 {"file_name": "spec.pdf"})
    assert "spec.pdf" in res and "knowledge edges" in res


async def test_local_list_workflows(svc, base_env, tmp_path):
    assert await svc.execute_tool("local-tools", "list_workflows", {}) == []
    d = tmp_path / "workflow_states"
    d.mkdir()
    (d / "a.json").write_text(json.dumps(
        {"workflow_id": "a", "name": "A", "description": "d",
         "trigger": "manual"}))
    (d / "bad.json").write_text("{not json")
    (d / "ignored.txt").write_text("x")
    res = await svc.execute_tool("local-tools", "list_workflows", {})
    assert res == [{"id": "a", "name": "A", "description": "d",
                    "trigger": "manual"}]


async def test_local_bridge_delegate(svc, base_env):
    bridge = MagicMock()
    bridge.process_incoming_message = AsyncMock(return_value={"sent": True})
    base_env.setattr(
        "integrations.universal_webhook_bridge.universal_webhook_bridge",
        bridge)
    assert await svc.execute_tool("local-tools", "bridge_agent_delegate",
                                  {"target_agent": "t", "message": "m"},
                                  {"agent_id": "a"}) == {"sent": True}
    err = await svc.execute_tool("local-tools", "bridge_agent_delegate", {})
    assert err["status"] == "error"


async def test_local_spawn_and_list_agents(svc, base_env):
    from core.models import AgentRegistry
    db = MagicMock()
    db.query.return_value.all.return_value = [
        SimpleNamespace(id="ag1", name="A", description="d", category="c")]
    sess = mk_session()
    sess.db.query.return_value.all.return_value = [
        SimpleNamespace(id="ag1", name="A", description="d", category="c")]
    base_env.setattr("core.database.SessionLocal", sess)
    base_env.setattr("core.atom_meta_agent.SpecialtyAgentTemplate",
                     SimpleNamespace(TEMPLATES=[{"name": "T"}]))
    res = await svc.execute_tool("local-tools", "list_agents", {})
    assert res["templates"] == [{"name": "T"}] and res["registered"][0]["id"] == "ag1"
    atom = MagicMock()
    atom.spawn_agent = AsyncMock(return_value={"agent": "new"})
    base_env.setattr("core.atom_meta_agent.get_atom_agent", lambda ws: atom)
    res = await svc.execute_tool("local-tools", "spawn_agent",
                                 {"template": "T"}, {"workspace_id": "w"})
    assert res == {"agent": "new"}


# ============================================================================
# Shopify
# ============================================================================
def _shopify_env(base_env, has_store=True, orders=None):
    sess = mk_session()
    if has_store:
        sess.db.query.return_value.filter.return_value.first.return_value = \
            SimpleNamespace(access_token="tok", shop_domain="shop")
    base_env.setattr("core.database.SessionLocal", sess)
    shopify = MagicMock()
    shopify.get_orders = AsyncMock(return_value=orders or [])
    base_env.setattr("integrations.shopify_service.ShopifyService",
                     lambda tenant_id=None: shopify)
    return shopify


async def test_shopify_no_store(svc, base_env):
    _shopify_env(base_env, has_store=False)
    res = await svc.execute_tool("local-tools", "shopify_create_product",
                                 {}, {"workspace_id": "w"})
    assert "No Shopify store connected" in res


async def test_shopify_create_product_and_inventory(svc, base_env):
    # Current contract: create_product delegates to ShopifyService (async);
    # update_inventory still uses the inline httpx client.
    shopify = _shopify_env(base_env)
    shopify.create_product = AsyncMock(
        return_value={"id": 9, "title": "Widget", "handle": "widget"}
    )
    res = await svc.execute_tool(
        "local-tools", "shopify_create_product", {}, {"workspace_id": "w"})
    assert "Product created successfully" in res
    assert "id=9" in res
    assert "title=Widget" in res
    assert "handle=widget" in res
    shopify.create_product = AsyncMock(side_effect=RuntimeError("shopify 500"))
    with pytest.raises(RuntimeError, match="shopify 500"):
        await svc.execute_tool(
            "local-tools", "shopify_create_product", {}, {"workspace_id": "w"})
    base_env.setattr(
        mcp_mod.httpx, "AsyncClient",
        fake_httpx_client(post_resp=http_response(200)))
    assert "Inventory updated" in await svc.execute_tool(
        "local-tools", "shopify_update_inventory", {}, {"workspace_id": "w"})
    base_env.setattr(
        mcp_mod.httpx, "AsyncClient",
        fake_httpx_client(post_resp=http_response(400, text="bad")))
    assert "Failed to update inventory" in await svc.execute_tool(
        "local-tools", "shopify_update_inventory", {}, {"workspace_id": "w"})


async def test_shopify_get_orders(svc, base_env):
    _shopify_env(base_env, orders=[{"order_number": 1, "total_price": "10",
                                    "currency": "USD",
                                    "financial_status": "paid"}])
    res = await svc.execute_tool("local-tools", "shopify_get_orders",
                                 {"limit": 1}, {"workspace_id": "w"})
    assert "Order #1" in res
    _shopify_env(base_env, orders=[])
    assert await svc.execute_tool("local-tools", "shopify_get_orders",
                                  {}, {"workspace_id": "w"}) == "No orders found."


# ============================================================================
# Browser tools
# ============================================================================
def _desktop_env(base_env, sent=True):
    nm = MagicMock()
    nm.send_to_desktop = AsyncMock(return_value=sent)
    base_env.setattr("core.notification_manager.notification_manager", nm)
    return nm


async def test_browser_desktop_modes(svc, base_env):
    _desktop_env(base_env, sent=True)
    assert "Command sent" in await svc.execute_tool(
        "local-tools", "browser_navigate", {"url": "http://x"})
    assert "Command sent" in await svc.execute_tool(
        "local-tools", "browser_click", {"selector": "#a", "x": 1, "y": 2})
    assert "Command sent" in await svc.execute_tool(
        "local-tools", "browser_type", {"text": "hi", "selector": "#a"})
    assert "Screenshot requested" in await svc.execute_tool(
        "local-tools", "browser_screenshot", {})
    _desktop_env(base_env, sent=False)
    assert "[SIMULATION] Navigated" in await svc.execute_tool(
        "local-tools", "browser_navigate", {"url": "http://x"})
    assert "[SIMULATION] Clicked" in await svc.execute_tool(
        "local-tools", "browser_click", {"selector": "#a"})
    assert "[SIMULATION] Typed" in await svc.execute_tool(
        "local-tools", "browser_type", {"text": "hi"})
    assert "[SIMULATION] Screenshot" in await svc.execute_tool(
        "local-tools", "browser_screenshot", {})


def _cloud_module(base_env):
    cb = MagicMock()
    cb.navigate = AsyncMock(return_value="nav")
    cb.click = AsyncMock(return_value="click")
    cb.type_text = AsyncMock(return_value="typed")
    cb.screenshot = AsyncMock(return_value="shot")
    cb.new_tab = AsyncMock(return_value="tab")
    cb.switch_tab = AsyncMock(return_value="switched")
    cb.click_coords = AsyncMock(return_value="coords")
    cb.list_tabs = AsyncMock(return_value=["t"])
    cb.save_session = AsyncMock(return_value="saved")
    cb.set_proxy = AsyncMock(return_value="proxy")
    cb.start_monitoring = AsyncMock(return_value="monitor-on")
    cb.stop_monitoring = AsyncMock(return_value="monitor-off")
    cb.wait_for_selector = AsyncMock(return_value="waited")
    cb.extract_content = AsyncMock(return_value="extracted")
    cb.upload_file = AsyncMock(return_value="uploaded")
    cb.download_file = AsyncMock(return_value="downloaded")
    fake = SimpleNamespace(cloud_browser=cb)
    base_env.setitem(sys.modules, "core.cloud_browser_service", fake)
    return cb


async def test_browser_cloud_modes(svc, base_env):
    _cloud_module(base_env)
    ctx = {"computer_use_mode": "cloud", "workspace_id": "default",
           "agent_id": "sess"}
    assert await svc.execute_tool("local-tools", "browser_navigate",
                                  {"url": "u"}, ctx) == "nav"
    assert await svc.execute_tool("local-tools", "browser_click",
                                  {"selector": "s"}, ctx) == "click"
    assert await svc.execute_tool("local-tools", "browser_type",
                                  {"text": "t"}, ctx) == "typed"
    assert await svc.execute_tool("local-tools", "browser_screenshot",
                                  {}, ctx) == "shot"
    assert await svc.execute_tool("local-tools", "browser_new_tab",
                                  {"url": "u"}, ctx) == "tab"
    assert await svc.execute_tool("local-tools", "browser_switch_tab",
                                  {"index": 1}, ctx) == "switched"
    assert await svc.execute_tool("local-tools", "browser_click_coords",
                                  {"x": "1", "y": "2"}, ctx) == "coords"
    assert await svc.execute_tool("local-tools", "list_browser_tabs",
                                  {}, ctx) == ["t"]
    assert await svc.execute_tool("local-tools", "browser_save_session",
                                  {}, ctx) == "saved"
    assert await svc.execute_tool("local-tools", "browser_set_proxy",
                                  {"server": "s"}, ctx) == "proxy"
    assert await svc.execute_tool("local-tools", "browser_monitor",
                                  {"active": True}, ctx) == "monitor-on"
    assert await svc.execute_tool("local-tools", "browser_monitor",
                                  {"active": False}, ctx) == "monitor-off"
    assert await svc.execute_tool("local-tools", "browser_wait_for_selector",
                                  {"selector": "s", "timeout": 1}, ctx) == "waited"
    assert await svc.execute_tool("local-tools", "browser_extract_content",
                                  {"selector": "s"}, ctx) == "extracted"
    assert await svc.execute_tool("local-tools", "browser_upload_file",
                                  {"selector": "s", "file_path": "/f"}, ctx) == "uploaded"
    assert await svc.execute_tool("local-tools", "browser_download_file",
                                  {"url": "u", "filename": "f"}, ctx) == "downloaded"


async def test_browser_cloud_tier_restriction(svc, base_env):
    _cloud_module(base_env)
    ctx = {"computer_use_mode": "cloud", "workspace_id": "w-enterprise",
           "agent_id": "s"}
    # tenant/plan lookup finds nothing -> restricted message
    for tool, args in [("browser_navigate", {"url": "u"}),
                       ("browser_click", {"selector": "s"}),
                       ("browser_type", {"text": "t"}),
                       ("browser_screenshot", {}),
                       ("browser_new_tab", {"url": "u"}),
                       ("browser_switch_tab", {"index": 0}),
                       ("browser_click_coords", {"x": "1", "y": "1"}),
                       ("list_browser_tabs", {}),
                       ("browser_save_session", {}),
                       ("browser_set_proxy", {"server": "s"}),
                       ("browser_monitor", {}),
                       ("browser_wait_for_selector", {"selector": "s"}),
                       ("browser_extract_content", {"selector": "s"}),
                       ("browser_upload_file", {"selector": "s"}),
                       ("browser_download_file", {"url": "u"})]:
        res = await svc.execute_tool("local-tools", tool, args, ctx)
        assert "restricted" in res, tool
    # desktop-mode-only refusal messages
    for tool in ["browser_new_tab", "browser_switch_tab", "browser_click_coords",
                 "list_browser_tabs", "browser_save_session", "browser_set_proxy",
                 "browser_monitor", "browser_wait_for_selector",
                 "browser_extract_content", "browser_upload_file",
                 "browser_download_file"]:
        res = await svc.execute_tool("local-tools", tool, {}, {})
        assert "only available in cloud mode" in res, tool


async def test_browser_cloud_module_missing(svc, base_env):
    import builtins
    real_import = builtins.__import__

    def blocked(name, *a, **k):
        if name == "core.cloud_browser_service":
            raise ImportError("no cloud browser")
        return real_import(name, *a, **k)
    base_env.setattr(builtins, "__import__", blocked)
    ctx = {"computer_use_mode": "cloud", "workspace_id": "default"}
    for tool in ["browser_navigate", "browser_click", "browser_type",
                 "browser_screenshot", "browser_new_tab", "browser_switch_tab",
                 "browser_click_coords", "list_browser_tabs",
                 "browser_save_session", "browser_set_proxy", "browser_monitor",
                 "browser_wait_for_selector", "browser_extract_content",
                 "browser_upload_file", "browser_download_file"]:
        res = await svc.execute_tool("local-tools", tool,
                                     {"url": "u", "selector": "s",
                                      "text": "t"}, ctx)
        assert "not available" in res, tool


def _model_query(first):
    q = MagicMock()
    q.first.return_value = first
    # any chain of .filter() calls resolves back to q (AgentRegistry queries
    # filter twice)
    q.filter = Mock(return_value=q)
    return q


async def test_cloud_access_enterprise_granted(svc, base_env):
    from core.models import Tenant, Workspace, PlanType
    cb = _cloud_module(base_env)
    ws = SimpleNamespace(tenant_id="t")
    tenant = SimpleNamespace(plan_type=PlanType.ENTERPRISE)
    sess = mk_session()
    qmap = {Workspace: _model_query(ws), Tenant: _model_query(tenant)}
    sess.db.query.side_effect = lambda m: qmap.get(
        m, _model_query(None))
    base_env.setattr("core.database.SessionLocal", sess)
    ctx = {"computer_use_mode": "cloud", "workspace_id": "w"}
    assert await svc.execute_tool("local-tools", "browser_navigate",
                                  {"url": "u"}, ctx) == "nav"
    # lookup raising also fails closed
    sess2 = MagicMock(side_effect=RuntimeError("db down"))
    base_env.setattr("core.database.SessionLocal", sess2)
    res = await svc.execute_tool("local-tools", "browser_navigate",
                                 {"url": "u"}, ctx)
    assert "restricted" in res


# ============================================================================
# UniversalIntegrationService-backed tools
# ============================================================================
@pytest.fixture
def uis(base_env):
    inst = MagicMock()
    inst.search = AsyncMock(return_value={"results": []})
    inst.execute = AsyncMock(return_value={"status": "success"})
    base_env.setattr(
        "integrations.universal_integration_service.UniversalIntegrationService",
        lambda: inst)
    singleton = MagicMock()
    singleton.search = AsyncMock(return_value={"results": []})
    singleton.execute = AsyncMock(return_value={"status": "success"})
    base_env.setattr(
        "integrations.universal_integration_service."
        "universal_integration_service", singleton)
    return SimpleNamespace(cls=inst, singleton=singleton)


async def test_crm_tools(svc, uis):
    assert await svc.execute_tool("local-tools", "search_contacts",
                                  {"query": "q", "platform": "salesforce"}) \
        == {"results": []}
    uis.cls.search = AsyncMock(side_effect=RuntimeError("down"))
    res = await svc.execute_tool("local-tools", "search_contacts",
                                 {"query": "q"})
    assert res == {}
    err = await svc.execute_tool("local-tools", "create_crm_lead", {})
    assert err == {"error": "platform is required"}
    assert await svc.execute_tool("local-tools", "create_crm_lead",
                                  {"platform": "hubspot", "email": "e@x"})
    uis.cls.execute = AsyncMock(return_value={"status": "success", "data": [
        {"Name": "D", "Amount": 5, "StageName": "Open"}]})
    pipeline = await svc.execute_tool("local-tools", "get_sales_pipeline",
                                      {"platform": "salesforce"})
    assert pipeline[0]["deal"] == "D"
    uis.cls.execute = AsyncMock(return_value={"status": "success", "data": [
        {"properties": {"dealname": "H", "amount": "7",
                        "dealstage": "s"}}]})
    pipeline = await svc.execute_tool("local-tools", "get_sales_pipeline",
                                      {"platform": "hubspot"})
    assert pipeline[0]["value"] == 7.0
    uis.cls.execute = AsyncMock(side_effect=RuntimeError("x"))
    assert await svc.execute_tool("local-tools", "get_sales_pipeline",
                                  {"platform": "salesforce"}) == []


async def test_project_tools(svc, uis, base_env):
    assert await svc.execute_tool("local-tools", "get_tasks",
                                  {"platform": "jira"})
    res = await svc.execute_tool("local-tools", "get_tasks", {})
    assert set(res) == {"jira", "asana", "linear", "monday"}
    assert await svc.execute_tool("local-tools", "search_tasks",
                                  {"query": "q", "platform": "asana"})
    uis.cls.search = AsyncMock(side_effect=RuntimeError("x"))
    assert await svc.execute_tool("local-tools", "search_tasks",
                                  {"query": "q"}) == {}
    err = await svc.execute_tool("local-tools", "list_projects", {})
    assert err == {"error": "platform is required"}
    assert await svc.execute_tool("local-tools", "list_projects",
                                  {"platform": "jira"})
    # create_task: platform given
    assert await svc.execute_tool("local-tools", "create_task",
                                  {"platform": "linear"})
    # create_task: platform resolved from connections
    conn = MagicMock()
    conn.list_connections = AsyncMock(return_value=[
        SimpleNamespace(piece_name="slack"),
        SimpleNamespace(piece_name="jira")])
    base_env.setattr("core.connection_service.ConnectionService", lambda: conn)
    assert await svc.execute_tool("local-tools", "create_task",
                                  {"title": "T"}, {"user_id": "u"})
    conn.list_connections = AsyncMock(return_value=[])
    assert await svc.execute_tool("local-tools", "create_task", {}) \
        == {"error": "No project management platform connected."}


async def test_communication_tools(svc, uis, base_env):
    # R81b: healthy-policy path — HITL allows (None) so tool execution proceeds.
    svc._check_hitl_policy = AsyncMock(return_value=None)
    assert await svc.execute_tool("local-tools", "post_channel_message",
                                  {"platform": "slack", "channel": "c",
                                   "message": "m"}, {"workspace_id": "w"})
    err = await svc.execute_tool("local-tools", "post_channel_message",
                                 {"message": "m"}, {"workspace_id": "w"})
    assert err == {"error": "platform is required"}
    assert await svc.execute_tool("local-tools", "send_email",
                                  {"to": "a@b", "subject": "s", "body": "b"},
                                  {"workspace_id": "w"})
    # send_message: HITL intercept
    svc._check_hitl_policy = AsyncMock(return_value={"paused": True})
    assert await svc.execute_tool("local-tools", "send_message",
                                  {"message": "m"}, {"workspace_id": "w"}) \
        == {"paused": True}
    # send_message: no connected platform (restore HITL to allow)
    svc._check_hitl_policy = AsyncMock(return_value=None)
    conn = MagicMock()
    conn.list_connections = AsyncMock(return_value=[])
    base_env.setattr("core.connection_service.ConnectionService", lambda: conn)
    assert await svc.execute_tool("local-tools", "send_message",
                                  {"message": "m"}, {"workspace_id": "w"}) \
        == {"error": "No communication platform connected."}
    # send_message: routes to connected slack
    conn.list_connections = AsyncMock(return_value=[
        SimpleNamespace(piece_name="slack")])
    assert await svc.execute_tool("local-tools", "send_message",
                                  {"target": "t", "message": "m", "platform": "slack"},
                                  {"workspace_id": "w"})
    # email / post_channel_message HITL intercept branches
    svc._check_hitl_policy = AsyncMock(return_value={"paused": True})
    assert await svc.execute_tool("local-tools", "send_email",
                                  {"to": "a@b"}, {"workspace_id": "w"}) \
        == {"paused": True}
    assert await svc.execute_tool("local-tools", "post_channel_message",
                                  {"platform": "slack"}, {"workspace_id": "w"}) \
        == {"paused": True}


async def test_email_and_calendar_tools(svc, uis):
    assert await svc.execute_tool("local-tools", "search_emails",
                                  {"query": "q", "platform": "gmail"})
    res = await svc.execute_tool("local-tools", "search_emails",
                                 {"query": "q"})
    assert "gmail" in res
    uis.cls.search = AsyncMock(side_effect=RuntimeError("x"))
    assert await svc.execute_tool("local-tools", "unified_communication_search",
                                  {"query": "q"}) == {}
    assert await svc.execute_tool("local-tools", "list_calendar_events", {})
    assert await svc.execute_tool("local-tools", "create_calendar_event",
                                  {"title": "T"})


async def test_storage_tools(svc, uis):
    assert await svc.execute_tool("local-tools", "search_files",
                                  {"query": "q", "platform": "notion"})
    uis.cls.search = AsyncMock(side_effect=RuntimeError("x"))
    res = await svc.execute_tool("local-tools", "search_files", {"query": "q"})
    assert res == {}
    assert await svc.execute_tool("local-tools", "list_files",
                                  {}) == {"error": "platform is required"}
    assert await svc.execute_tool("local-tools", "create_folder",
                                  {}) == {"error": "platform is required"}
    assert await svc.execute_tool("local-tools", "list_files",
                                  {"platform": "google_drive"})
    assert await svc.execute_tool("local-tools", "create_folder",
                                  {"platform": "google_drive"})


async def test_unified_knowledge_search(svc, base_env):
    entity = SimpleNamespace(
        entity_id="e1", canonical_name="Acme Corp",
        entity_type=SimpleNamespace(value="company"),
        source_platforms=[SimpleNamespace(value="hubspot")],
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    engine = MagicMock()
    engine.entity_registry = {"e1": entity}
    base_env.setattr("ai.data_intelligence.DataIntelligenceEngine",
                     lambda: engine)
    res = await svc.execute_tool("local-tools", "unified_knowledge_search",
                                 {"query": "acme"})
    assert res[0]["id"] == "e1"
    res = await svc.execute_tool("local-tools", "unified_knowledge_search",
                                 {"query": "zzz"})
    assert res == []


async def test_save_business_fact(svc, base_env):
    facts = {}

    class FakeFact:
        def __init__(self, **kw):
            self.__dict__.update(kw)
    wm = MagicMock()
    wm.record_business_fact = AsyncMock(return_value=True)
    base_env.setattr("core.agent_world_model.WorldModelService",
                     lambda ws: wm)
    base_env.setattr("core.agent_world_model.BusinessFact", FakeFact)
    res = await svc.execute_tool("local-tools", "save_business_fact",
                                 {"fact": "F", "citations": []},
                                 {"workspace_id": "w"})
    assert res == "Fact saved: F"
    wm.record_business_fact = AsyncMock(return_value=False)
    assert await svc.execute_tool("local-tools", "save_business_fact",
                                  {"fact": "F"}) == "Failed to save fact."


async def test_verify_citation(svc, tmp_path):
    good = tmp_path / "cite.txt"
    good.write_text("hello world")
    # tmp_path is under pytest's basetemp which is /private/var/...; craft a
    # /tmp path instead for the allowlist check
    allowed = "/tmp/w85_cite.txt"
    with open(allowed, "w") as f:
        f.write("hello world")
    assert "Path required" in await svc.execute_tool(
        "local-tools", "verify_citation", {})
    assert "Access denied" in await svc.execute_tool(
        "local-tools", "verify_citation", {"path": "/etc/passwd"})
    res = await svc.execute_tool("local-tools", "verify_citation",
                                 {"path": allowed})
    assert "Verified" in res and "hello world" in res
    unreadable = "/tmp/w85_dir_cite"
    os.makedirs(unreadable, exist_ok=True)
    res = await svc.execute_tool("local-tools", "verify_citation",
                                 {"path": unreadable})
    assert "failed to read" in res
    assert "NOT found" in await svc.execute_tool(
        "local-tools", "verify_citation", {"path": "/tmp/w85_missing.txt"})


async def test_support_and_dev_tools(svc, uis):
    assert await svc.execute_tool("local-tools", "search_tickets",
                                  {"query": "q", "platform": "zendesk"})
    assert await svc.execute_tool("local-tools", "create_ticket",
                                  {}) == {"error": "platform is required"}
    assert await svc.execute_tool("local-tools", "create_ticket",
                                  {"platform": "zendesk"})
    assert await svc.execute_tool("local-tools", "search_repositories",
                                  {"query": "q", "platform": "github"})
    uis.cls.search = AsyncMock(side_effect=RuntimeError("x"))
    assert await svc.execute_tool("local-tools", "search_tickets",
                                  {"query": "q"}) == {}
    assert await svc.execute_tool("local-tools", "search_repositories",
                                  {"query": "q"}) == {}
    uis.cls.search = AsyncMock(return_value={"results": []})
    assert await svc.execute_tool("local-tools", "search_designs",
                                  {"query": "q"})


async def test_finance_tools(svc, uis):
    assert await svc.execute_tool("local-tools", "query_financial_metrics",
                                  {"period": "2026-01"})
    assert await svc.execute_tool("local-tools", "list_finance_invoices",
                                  {"platform": "stripe"})
    uis.cls.execute = AsyncMock(side_effect=RuntimeError("x"))
    assert await svc.execute_tool("local-tools", "list_finance_invoices",
                                  {}) == {}


async def test_get_inventory_levels(svc, base_env):
    conn = MagicMock()
    conn.list_connections = AsyncMock(return_value=[
        SimpleNamespace(piece_name="shopify", credentials={"access_token": "t"},
                        connection_metadata={"shop_url": "s"}),
        SimpleNamespace(piece_name="zoho_inventory",
                        credentials={"access_token": "zt"},
                        connection_metadata={"organization_id": "o"}),
    ])
    base_env.setattr("core.connection_service.ConnectionService", lambda: conn)
    shopify = MagicMock()
    shopify.get_inventory_levels = AsyncMock(return_value=[{"sku": "x"}])
    base_env.setattr("integrations.shopify_service.ShopifyService",
                     lambda tenant_id=None: shopify)
    zoho = MagicMock()
    zoho.get_inventory_levels = AsyncMock(return_value=[{"sku": "z"}])
    base_env.setattr(
        "integrations.zoho_inventory_service.zoho_inventory_service", zoho)
    res = await svc.execute_tool("local-tools", "get_inventory_levels",
                                 {}, {"user_id": "u"})
    assert {"sku": "x"} in res and {"sku": "z"} in res
    res = await svc.execute_tool("local-tools", "get_inventory_levels",
                                 {"platform": "zoho"}, {"user_id": "u"})
    assert res == [{"sku": "z"}]


async def test_search_dashboards(svc, uis):
    assert await svc.execute_tool("local-tools", "search_dashboards",
                                  {"query": "q", "platform": "tableau"})
    uis.cls.search = AsyncMock(side_effect=RuntimeError("x"))
    assert await svc.execute_tool("local-tools", "search_dashboards",
                                  {"query": "q"}) == {}


async def test_whatsapp_send_message(svc, base_env):
    # R81b: allow via healthy HITL mock (whatsapp_send_message is risky-gated).
    svc._check_hitl_policy = AsyncMock(return_value=None)
    mgr = MagicMock()
    mgr.status = "connected"
    mgr.integration = MagicMock()
    mgr.integration.send_message = AsyncMock(return_value={"sent": True})
    base_env.setattr(
        "integrations.whatsapp_service_manager.whatsapp_service_manager", mgr)
    assert await svc.execute_tool("local-tools", "whatsapp_send_message",
                                  {"to": "+1", "message": "m"},
                                  {"workspace_id": "w"}) == {"sent": True}
    del mgr.integration.send_message
    assert "not found" in (await svc.execute_tool(
        "local-tools", "whatsapp_send_message", {"to": "+1"},
        {"workspace_id": "w"}))["error"]
    mgr.status = "disconnected"
    mgr.initialize_service = AsyncMock(return_value=None)
    assert "unavailable" in (await svc.execute_tool(
        "local-tools", "whatsapp_send_message", {"to": "+1"},
        {"workspace_id": "w"}))["error"]
    base_env.setattr(
        "integrations.whatsapp_service_manager.whatsapp_service_manager",
        MagicMock(status="connected", integration=None,
                  initialize_service=AsyncMock(side_effect=ImportError("x"))))
    assert "not found" in (await svc.execute_tool(
        "local-tools", "whatsapp_send_message", {},
        {"workspace_id": "w"}))["error"]
    class _Boom:
        status = "connected"
        integration = SimpleNamespace(
            send_message=AsyncMock(side_effect=RuntimeError("boom")))
        async def initialize_service(self):
            self.status = "connected"
    base_env.setattr(
        "integrations.whatsapp_service_manager.whatsapp_service_manager",
        _Boom())
    assert "Failed" in (await svc.execute_tool(
        "local-tools", "whatsapp_send_message", {},
        {"workspace_id": "w"}))["error"]


async def test_create_zoom_meeting(svc, base_env):
    conn = MagicMock()
    conn.list_connections = AsyncMock(return_value=[])
    base_env.setattr("core.connection_service.ConnectionService", lambda: conn)
    assert await svc.execute_tool("local-tools", "create_zoom_meeting",
                                  {}) == {"error": "Zoom not connected"}
    conn.list_connections = AsyncMock(return_value=[
        SimpleNamespace(piece_name="zoom",
                        credentials={"access_token": "tok"})])
    zoom = MagicMock()
    zoom.create_meeting = AsyncMock(return_value={"id": 1})
    base_env.setattr("integrations.zoom_service.ZoomService",
                     lambda tenant_id=None: zoom)
    assert await svc.execute_tool("local-tools", "create_zoom_meeting",
                                  {}, {"tenant_id": "t"}) == {"id": 1}


async def test_get_system_health(svc, base_env):
    cb = MagicMock()
    cb.get_stats.return_value = {"s": 1}
    cb.get_all_stats.return_value = {"all": 1}
    base_env.setattr("core.circuit_breaker.circuit_breaker", cb)
    analyzer = MagicMock()
    analyzer.analyze_service_drift.return_value = {"drift": 1}
    analyzer.get_global_performance_report.return_value = {"report": 1}
    base_env.setattr("core.analytics_engine.get_analytics_engine",
                     lambda: analyzer)
    res = await svc.execute_tool("local-tools", "get_system_health",
                                 {"service": "shopify"})
    assert res == {"stats": {"s": 1}, "drift": {"drift": 1}}
    res = await svc.execute_tool("local-tools", "get_system_health", {})
    assert res["circuit_breaker"] == {"all": 1}


async def test_generate_pdf_report(svc, tmp_path):
    res = await svc.execute_tool("local-tools", "generate_pdf_report",
                                 {"content": "line one\nline two",
                                  "filename": "../../evil"})
    assert res["status"] == "success"
    assert res["file_path"] == "/tmp/evil.pdf"
    res = await svc.execute_tool("local-tools", "generate_pdf_report",
                                 {"content": "x"})
    assert res["file_path"] == "/tmp/report.pdf"


async def test_marketing_tools(svc, base_env):
    mkt = MagicMock()
    mkt.manage_google_reviews = AsyncMock(return_value="reviews")
    mkt.request_testimonial = AsyncMock(return_value="testimonial")
    mkt.run_ads_check = AsyncMock(return_value="ads")
    base_env.setattr("core.marketing_agent.MarketingAgent", lambda: mkt)
    ctx = {"workspace_id": "w"}
    assert await svc.execute_tool("local-tools", "manage_reviews", {}, ctx) \
        == "reviews"
    assert await svc.execute_tool("local-tools", "request_testimonial",
                                  {"customer_id": "c"}, ctx) == "testimonial"
    assert await svc.execute_tool("local-tools", "analyze_ads_performance",
                                  {"service": "meta_ads"}, ctx) == "ads"


async def test_sales_tools_import_missing(svc):
    for tool in ["score_lead", "draft_sales_outreach", "monitor_pipeline_health"]:
        res = await svc.execute_tool("local-tools", tool, {},
                                     {"workspace_id": "w"})
        assert res["status"] == "error" and tool in res["error"]


async def test_shipping_tools(svc, uis, base_env):
    assert await svc.execute_tool("local-tools", "track_shipment",
                                  {"platform": "shippo",
                                   "tracking_number": "1Z"})
    conn = MagicMock()
    conn.list_connections = AsyncMock(return_value=[
        SimpleNamespace(piece_name="fedex")])
    base_env.setattr("core.connection_service.ConnectionService", lambda: conn)
    assert await svc.execute_tool("local-tools", "create_shipment",
                                  {}, {"user_id": "u"})
    conn.list_connections = AsyncMock(return_value=[])
    err = await svc.execute_tool("local-tools", "create_shipment", {},
                                 {"user_id": "u"})
    assert "No shipping platform connected" in err["error"]


async def test_cloud_provider_tools(svc, uis):
    for tool in ["s3_upload", "s3_download", "lambda_invoke", "sqs_send",
                 "sns_publish"]:
        assert await svc.execute_tool("local-tools", tool, {})
    for tool in ["azure_blob_upload", "azure_blob_download",
                 "azure_function_invoke"]:
        assert await svc.execute_tool("local-tools", tool, {})
    for tool in ["gcs_upload", "gcs_download", "cloud_function_invoke",
                 "pubsub_publish"]:
        assert await svc.execute_tool("local-tools", tool, {})


# ============================================================================
# Knowledge & memory tools
# ============================================================================
@pytest.fixture
def knowledge(base_env):
    mgr = MagicMock()
    mgr.process_document = AsyncMock(
        return_value={"entities": 2, "relationships": 1})
    mgr.query_graphrag = Mock(return_value={"answer": "a"})
    base_env.setattr("core.knowledge_ingestion.get_knowledge_ingestion",
                     lambda: mgr)
    proc = MagicMock()
    proc.process_document = AsyncMock(
        return_value={"success": True, "content": "text body",
                      "page_count": 2, "total_chars": 9, "tables": [[]]})
    base_env.setattr("core.docling_processor.get_docling_processor",
                     lambda: proc)
    return SimpleNamespace(ingestion=mgr, processor=proc)


async def test_ingest_knowledge_from_text(svc, knowledge):
    assert (await svc.execute_tool("local-tools", "ingest_knowledge_from_text",
                                   {}))["error"] == "Text content is required"
    res = await svc.execute_tool("local-tools", "ingest_knowledge_from_text",
                                 {"text": "hello"}, {"workspace_id": "w"})
    assert res == {"success": True, "stats": {"entities": 2,
                                              "relationships": 1}}


async def test_ingest_knowledge_from_file(svc, knowledge, base_env, tmp_path):
    assert (await svc.execute_tool("local-tools",
                                   "ingest_knowledge_from_file",
                                   {}))["error"] == "File path is required"
    assert (await svc.execute_tool(
        "local-tools", "ingest_knowledge_from_file",
        {"file_path": "/no/such/file.xlsx"}))["error"].startswith("File not found")
    f = tmp_path / "sheet.xlsx"
    f.write_text("x")
    # parse failure
    knowledge.processor.process_document = AsyncMock(
        return_value={"success": False, "error": "bad pdf"})
    assert "File parsing failed" in (await svc.execute_tool(
        "local-tools", "ingest_knowledge_from_file",
        {"file_path": str(f)}))["error"]
    # no content
    knowledge.processor.process_document = AsyncMock(
        return_value={"success": True, "content": ""})
    assert "No content" in (await svc.execute_tool(
        "local-tools", "ingest_knowledge_from_file",
        {"file_path": str(f)}))["error"]
    # formulas ok
    knowledge.processor.process_document = AsyncMock(
        return_value={"success": True, "content": "c", "page_count": 1,
                      "total_chars": 1, "tables": []})
    ext = MagicMock()
    ext.extract_from_file = Mock(return_value=[
        {"name": "n", "expression": "e", "domain": "d"}])
    base_env.setattr("core.formula_extractor.get_formula_extractor",
                     lambda ws: ext)
    res = await svc.execute_tool("local-tools", "ingest_knowledge_from_file",
                                 {"file_path": str(f)},
                                 {"workspace_id": "w"})
    assert res["success"] and res["file_stats"]["formulas_extracted"] == 1
    # formulas raise -> warning branch
    ext.extract_from_file = Mock(side_effect=RuntimeError("x"))
    res = await svc.execute_tool("local-tools", "ingest_knowledge_from_file",
                                 {"file_path": str(f)})
    assert res["extracted_formulas"] == []


async def test_search_formulas_and_graph(svc, base_env, knowledge):
    assert (await svc.execute_tool("local-tools", "search_formulas",
                                   {}))["error"] == "Search query is required"
    fm = MagicMock()
    fm.search_formulas = Mock(return_value=[{"name": "n"}])
    base_env.setattr("core.formula_memory.get_formula_manager",
                     lambda **kw: fm)
    res = await svc.execute_tool("local-tools", "search_formulas",
                                 {"query": "q"}, {"workspace_id": "w"})
    assert res == {"results": [{"name": "n"}]}
    assert (await svc.execute_tool("local-tools", "query_knowledge_graph",
                                   {}))["error"] == "Search query is required"
    res = await svc.execute_tool("local-tools", "query_knowledge_graph",
                                 {"query": "q", "mode": "local"})
    assert res == {"answer": "a"}


# ============================================================================
# Standardized granular tools
# ============================================================================
async def test_granular_tools(svc, uis):
    cases = [
        ("update_crm_lead", {"platform": "sf", "id": "1", "data": {}}),
        ("create_crm_deal", {"platform": "sf"}),
        ("update_crm_deal", {"platform": "sf", "id": "1"}),
        ("update_task", {"platform": "jira", "id": "1"}),
        ("create_support_ticket", {"platform": "zendesk"}),
        ("update_support_ticket", {"platform": "zendesk", "id": "1"}),
        ("create_ecommerce_order", {"platform": "shopify"}),
        ("upload_file_to_storage", {"platform": "gdrive"}),
        ("create_storage_folder", {"platform": "gdrive"}),
        ("add_marketing_subscriber", {"platform": "mailchimp"}),
        ("create_invoice", {"platform": "stripe"}),
        ("create_record", {"service": "sf", "entity": "lead"}),
        ("update_record", {"service": "sf", "entity": "lead", "id": "1"}),
        ("push_to_integration", {"service": "sf", "action": "create"}),
    ]
    for tool, args in cases:
        res = await svc.execute_tool("local-tools", tool, args)
        assert res == {"status": "success"}, tool
    assert uis.singleton.execute.await_count == len(cases)


async def test_discovery_tools(svc, uis, base_env):
    cs = MagicMock()
    cs.get_connections = Mock(return_value=[
        {"integration_id": "slack", "status": "active"},
        {"integration_id": "dead", "status": "revoked"},
    ])
    base_env.setattr("core.connection_service.connection_service", cs)
    res = await svc.execute_tool("local-tools", "discover_connections", {},
                                 {"user_id": "u"})
    assert res == {"active_integrations": ["slack"]}
    # global_search with explicit platforms (one failing)
    uis.singleton.search = AsyncMock(side_effect=RuntimeError("down"))
    res = await svc.execute_tool("local-tools", "global_search",
                                 {"query": "q", "platforms": ["slack", "sf"]})
    assert res["slack"]["status"] == "error"
    uis.singleton.search = AsyncMock(return_value={"results": []})
    res = await svc.execute_tool("local-tools", "global_search",
                                 {"query": "q"}, {"user_id": "u"})
    assert res == {"slack": {"results": []}}
    assert await svc.execute_tool("local-tools", "call_integration",
                                  {"service": "s", "action": "a"})
    res = await svc.execute_tool("local-tools", "list_integrations", {})
    assert res["native_count"] > 0


# ============================================================================
# WhatsApp template HTTP tools
# ============================================================================
def _wa_conn_env(base_env, creds):
    conn = MagicMock()
    conn.list_connections = AsyncMock(return_value=[
        SimpleNamespace(integration_id="whatsapp", credentials=creds)])
    base_env.setattr("core.connection_service.ConnectionService",
                     lambda: conn)


async def test_whatsapp_send_template(svc, base_env):
    conn = MagicMock()
    conn.list_connections = AsyncMock(return_value=[])
    base_env.setattr("core.connection_service.ConnectionService",
                     lambda: conn)
    assert (await svc.execute_tool("local-tools", "whatsapp_send_template",
                                   {}, {"user_id": "u"}))["error"] \
        == "WhatsApp Business not connected."
    _wa_conn_env(base_env, {"access_token": "t"})
    assert (await svc.execute_tool("local-tools", "whatsapp_send_template",
                                   {}, {"user_id": "u"}))["error"] \
        == "WhatsApp credentials incomplete."
    _wa_conn_env(base_env, {"access_token": "t", "phone_number_id": "p"})
    assert "required" in (await svc.execute_tool(
        "local-tools", "whatsapp_send_template", {},
        {"user_id": "u"}))["error"]
    base_env.setattr(
        mcp_mod.httpx, "AsyncClient",
        fake_httpx_client(post_resp=http_response(
            200, {"messages": [{"id": "m1"}]})))
    res = await svc.execute_tool("local-tools", "whatsapp_send_template",
                                 {"to": "+1", "template_name": "t"},
                                 {"user_id": "u"})
    assert res == {"success": True, "message_id": "m1"}
    base_env.setattr(
        mcp_mod.httpx, "AsyncClient",
        fake_httpx_client(post_resp=http_response(400, text="bad")))
    assert "WhatsApp API error" in (await svc.execute_tool(
        "local-tools", "whatsapp_send_template",
        {"to": "+1", "template_name": "t"}, {"user_id": "u"}))["error"]
    base_env.setattr(mcp_mod.httpx, "AsyncClient",
                     fake_httpx_client(exc=RuntimeError("net")))
    assert "Failed to send" in (await svc.execute_tool(
        "local-tools", "whatsapp_send_template",
        {"to": "+1", "template_name": "t"}, {"user_id": "u"}))["error"]


async def test_whatsapp_list_templates(svc, base_env):
    _wa_conn_env(base_env, {"access_token": "t"})
    assert (await svc.execute_tool("local-tools", "whatsapp_list_templates",
                                   {}, {"user_id": "u"}))["error"] \
        == "WhatsApp credentials incomplete."
    _wa_conn_env(base_env, {"access_token": "t", "waba_id": "w"})
    base_env.setattr(
        mcp_mod.httpx, "AsyncClient",
        fake_httpx_client(get_resp=http_response(
            200, {"data": [{"name": "n", "status": "s", "category": "c"}]})))
    res = await svc.execute_tool("local-tools", "whatsapp_list_templates",
                                 {}, {"user_id": "u"})
    assert res["templates"][0]["name"] == "n"
    base_env.setattr(
        mcp_mod.httpx, "AsyncClient",
        fake_httpx_client(get_resp=http_response(403, text="no")))
    assert "WhatsApp API error" in (await svc.execute_tool(
        "local-tools", "whatsapp_list_templates", {},
        {"user_id": "u"}))["error"]
    base_env.setattr(mcp_mod.httpx, "AsyncClient",
                     fake_httpx_client(exc=RuntimeError("net")))
    assert "Failed to list" in (await svc.execute_tool(
        "local-tools", "whatsapp_list_templates", {},
        {"user_id": "u"}))["error"]


async def test_unknown_tool_and_server(svc):
    res = await svc.execute_tool("local-tools", "totally_unknown", {})
    assert res["status"] == "not_implemented"
    res = await svc.execute_tool("weird-server", "x", {})
    assert res["status"] == "not_implemented"


# ============================================================================
# _check_hitl_policy
# ============================================================================
def _hitl_db(workspace, tenant, user=None, agent=None):
    from core.models import AgentRegistry, Tenant, User, Workspace
    db = MagicMock()
    qmap = {
        Workspace: _model_query(workspace),
        Tenant: _model_query(tenant),
        User: _model_query(user),
        AgentRegistry: _model_query(agent),
    }
    db.query.side_effect = lambda m: qmap.get(m, _model_query(None))
    cm = MagicMock()
    cm.__enter__.return_value = db
    cm.__exit__.return_value = False
    factory = MagicMock(return_value=cm)
    factory.db = db
    return factory


async def test_hitl_policy_paths(svc, base_env):
    from core.models import Tenant, Workspace
    # R81b: fail-closed — missing workspace/tenant now BLOCKS risky tools
    # instead of the old swallow-and-allow.
    base_env.setattr("core.database.SessionLocal", mk_session(first=None))
    blocked = await svc._check_hitl_policy("w", "send_email", {})
    assert blocked and blocked.get("blocked_by") == "hitl_policy_error"
    # workspace but no tenant
    base_env.setattr("core.database.SessionLocal",
                     _hitl_db(SimpleNamespace(tenant_id="t"), None))
    blocked = await svc._check_hitl_policy("w", "send_email", {})
    assert blocked and blocked.get("blocked_by") == "hitl_policy_error"
    # no governance requirement -> None
    base_env.setattr("core.database.SessionLocal",
                     _hitl_db(SimpleNamespace(tenant_id="t"),
                              SimpleNamespace(metadata_json={})))
    assert await svc._check_hitl_policy("w", "send_email", {}) is None
    # require_hitl + non-risky tool -> None
    gov = SimpleNamespace(metadata_json={"governance": {
        "require_hitl_external": True}})
    base_env.setattr("core.database.SessionLocal",
                     _hitl_db(SimpleNamespace(tenant_id="t"), gov))
    assert await svc._check_hitl_policy("w", "list_files", {}) is None


async def test_hitl_interception_and_autonomy(svc, base_env):
    from core.models import Tenant, Workspace
    gov = SimpleNamespace(metadata_json={"governance": {
        "require_hitl_external": True, "allow_autonomous_external": True,
        "roles": {"send_email": "manager"}}})
    # interception (no agent)
    base_env.setattr("core.database.SessionLocal",
                     _hitl_db(SimpleNamespace(tenant_id="t"), gov,
                              user=SimpleNamespace(
                                  tenant_id="t", notification_preferences={})))
    from core.intervention_service import intervention_service
    with patch.object(intervention_service, "request_intervention",
                      AsyncMock(return_value={"paused": True})) as ri:
        res = await svc._check_hitl_policy("w", "send_email",
                                           {"to": "x@y"}, {"user_id": "u1"})
        assert res == {"paused": True}
        ri.assert_awaited_once()
        assert "manager" in ri.call_args.kwargs["reason"]
    # user force-hitl blocks autonomy
    gov_force = SimpleNamespace(metadata_json={"governance": {
        "require_hitl_external": True, "allow_autonomous_external": True}})
    base_env.setattr("core.database.SessionLocal",
                     _hitl_db(SimpleNamespace(tenant_id="t"), gov_force,
                              user=SimpleNamespace(
                                  tenant_id="t",
                                  notification_preferences={
                                      "force_agent_approval": True}),
                              agent=SimpleNamespace(maturity_level=5, status="autonomous",
                                                     name="A")))
    with patch.object(intervention_service, "request_intervention",
                      AsyncMock(return_value={"paused": True})):
        assert await svc._check_hitl_policy(
            "w", "send_email", {}, {"user_id": "u", "agent_id": "a"}) \
            == {"paused": True}
    # maturity-5 agent + allow_autonomous + no user override -> allowed
    base_env.setattr("core.database.SessionLocal",
                     _hitl_db(SimpleNamespace(tenant_id="t"), gov_force,
                              user=SimpleNamespace(tenant_id="t",
                                                   notification_preferences={}),
                              agent=SimpleNamespace(maturity_level=5, status="autonomous",
                                                     name="A")))
    assert await svc._check_hitl_policy("w", "send_email", {},
                                        {"user_id": "u", "agent_id": "a"}) is None
    # low-maturity agent -> intercepted
    base_env.setattr("core.database.SessionLocal",
                     _hitl_db(SimpleNamespace(tenant_id="t"), gov_force,
                              user=SimpleNamespace(tenant_id="t",
                                                   notification_preferences={}),
                              agent=SimpleNamespace(maturity_level=2,
                                                     name="B")))
    with patch.object(intervention_service, "request_intervention",
                      AsyncMock(return_value={"paused": True})):
        assert await svc._check_hitl_policy("w", "send_email", {},
                                            {"user_id": "u"}) \
            == {"paused": True}


# ============================================================================
# Entity-bound execution + permissions + injection helpers
# ============================================================================
async def test_execute_entity_tool(svc, base_env):
    svc.execute_tool = AsyncMock(return_value="tool-result")
    res = await svc.execute_entity_tool(
        {"entity_id": "e1", "entity_type_slug": "vendor", "tenant_id": "t",
         "agent_id": "a", "entity_data": {"email": "x@y"},
         "workspace_id": "w"},
        "send_email", {"to": "entity.email"})
    assert res["status"] == "success" and res["result"] == "tool-result"
    args = svc.execute_tool.call_args[0]
    assert args[2]["to"] == "x@y"
    # missing required field
    err = await svc.execute_entity_tool({"entity_id": "e"}, "t", {})
    assert err["status"] == "error" and "missing" in err["error"]
    # underlying tool raising
    svc.execute_tool = AsyncMock(side_effect=RuntimeError("boom"))
    err = await svc.execute_entity_tool(
        {"entity_id": "e", "entity_type_slug": "v", "tenant_id": "t"},
        "t", {})
    assert err["status"] == "error"


def test_inject_entity_context_and_nested(svc):
    ctx = SimpleNamespace(entity_data={"a": {"b": {"c": 5}}})
    out = svc._inject_entity_context(
        {"x": "entity.a.b.c", "y": "literal", "n": 3}, ctx)
    assert out == {"x": 5, "y": "literal", "n": 3}
    assert svc._get_nested_field({"a": 1}, "a") == 1
    assert svc._get_nested_field({"a": 1}, "a.b") is None
    assert svc._get_nested_field(None, "a") is None


def test_check_entity_skill_permission(svc, base_env):
    from core.models import Skill
    skill_service = MagicMock()
    skill_service.check_skill_permission = Mock(
        return_value={"allowed": True, "reason": "ok"})
    base_env.setattr("core.entity_skill_service.get_entity_skill_service",
                     lambda: skill_service)
    sess = mk_session()
    sess.db.query.return_value.filter.return_value.first.return_value = \
        SimpleNamespace(name="My Skill")
    base_env.setattr("core.database.SessionLocal", sess)
    res = svc.check_entity_skill_permission("t", "vendor", "s1")
    assert res["allowed"] is True and res["skill_name"] == "My Skill"
    # cache hit
    assert svc.check_entity_skill_permission("t", "vendor", "s1") == res
    # exception branch
    base_env.setattr("core.entity_skill_service.get_entity_skill_service",
                     Mock(side_effect=RuntimeError("boom")))
    err = svc.check_entity_skill_permission("t", "vendor", "s2")
    assert err["allowed"] is False


# ============================================================================
# web_search
# ============================================================================
async def test_web_search_paths(svc, base_env):
    # no key configured
    res = await svc.web_search("q")
    assert "not configured" in res["error"]
    # env key + successful Tavily call
    base_env.setenv("TAVILY_API_KEY", "env-key")
    base_env.setattr(
        mcp_mod.httpx, "AsyncClient",
        fake_httpx_client(post_resp=http_response(200, {"answer": "a"})))
    assert await svc.web_search("q") == {"answer": "a"}
    # non-200 -> falls through to unconfigured error dict
    base_env.setattr(
        mcp_mod.httpx, "AsyncClient",
        fake_httpx_client(post_resp=http_response(500, text="bad")))
    assert "not configured" in (await svc.web_search("q"))["error"]
    # exception -> fallback
    base_env.setattr(mcp_mod.httpx, "AsyncClient",
                     fake_httpx_client(exc=RuntimeError("net")))
    assert "not configured" in (await svc.web_search("q"))["error"]
    base_env.delenv("TAVILY_API_KEY")
    # BYOK path: manager returns tenant key
    byok = MagicMock()
    byok.get_tenant_api_key = Mock(return_value="byok-key")
    base_env.setattr(mcp_mod, "get_byok_manager", lambda: byok)
    base_env.setattr(
        mcp_mod.httpx, "AsyncClient",
        fake_httpx_client(post_resp=http_response(200, {"answer": "b"})))
    assert await svc.web_search("q", tenant_id="t1") == {"answer": "b"}
    # BYOK raising -> falls back to env / unconfigured
    byok.get_tenant_api_key = Mock(side_effect=RuntimeError("x"))
    assert "not configured" in (await svc.web_search("q", tenant_id="t1")
                                )["error"]
