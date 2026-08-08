"""TDD bug-hunt: mcp_service local tools with phantom singletons (R88 follow-up).

Reported by the coverage agent (read-only at the time):
- unified_knowledge_search: `from ai.data_intelligence import engine` —
  `engine` exists only under `__main__` → always ImportError (HIGH)
- create_zoom_meeting: `from integrations.zoom_service import zoom_service` —
  no module singleton → always ImportError (HIGH)
- get_system_health: `from core.analytics_engine import analyzer` — no module
  singleton → always ImportError (HIGH)
- get_inventory_levels: shopify_service singleton missing → ImportError
  whenever a shopify connection exists (MED)
- search_formulas: get_formula_manager(tenant_id=...) — signature is
  workspace_id → always TypeError (MED)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

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


@pytest.mark.asyncio
async def test_unified_knowledge_search_uses_engine_class(svc, monkeypatch):
    engine = MagicMock()
    engine.entity_registry.values.return_value = []
    cls = MagicMock(return_value=engine)
    monkeypatch.setattr("ai.data_intelligence.DataIntelligenceEngine", cls)

    result = await svc.execute_tool(
        "local-tools", "unified_knowledge_search", {"query": "alpha"}, {}
    )

    assert result == []
    cls.assert_called_once()


@pytest.mark.asyncio
async def test_create_zoom_meeting_with_connection(svc, monkeypatch):
    conn = MagicMock()
    conn.piece_name = "zoom"
    conn.credentials = {"access_token": "t"}
    conn_cls = MagicMock()
    conn_cls.return_value.list_connections = AsyncMock(return_value=[conn])
    monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)

    zoom = MagicMock()
    zoom.create_meeting = AsyncMock(return_value={"id": "m1"})
    zoom_cls = MagicMock(return_value=zoom)
    monkeypatch.setattr("integrations.zoom_service.ZoomService", zoom_cls)

    result = await svc.execute_tool(
        "local-tools", "create_zoom_meeting", {"topic": "T", "duration": 30}, {"user_id": "u"}
    )

    assert result == {"id": "m1"}
    zoom.create_meeting.assert_awaited_once()
    assert zoom_cls.call_args.kwargs.get("tenant_id") or zoom_cls.call_args.args


@pytest.mark.asyncio
async def test_get_system_health_with_service(svc, monkeypatch):
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
async def test_get_system_health_global(svc, monkeypatch):
    cb = MagicMock()
    cb.get_all_stats = MagicMock(return_value={"all": 1})
    monkeypatch.setattr("core.circuit_breaker.circuit_breaker", cb)
    analytics = MagicMock()
    analytics.get_global_performance_report = MagicMock(return_value={"ok": True})
    monkeypatch.setattr("core.analytics_engine.get_analytics_engine", lambda: analytics)

    result = await svc.execute_tool("local-tools", "get_system_health", {}, {})

    assert result == {"circuit_breaker": {"all": 1}, "global_report": {"ok": True}}


@pytest.mark.asyncio
async def test_get_inventory_levels_with_shopify_connection(svc, monkeypatch):
    conn = MagicMock()
    conn.piece_name = "shopify"
    conn.credentials = {"access_token": "t"}
    conn.metadata = {"shop_url": "s.myshopify.com"}
    conn_cls = MagicMock()
    conn_cls.return_value.list_connections = AsyncMock(return_value=[conn])
    monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)

    shopify = MagicMock()
    shopify.get_inventory_levels = AsyncMock(return_value=[{"id": 1}])
    shopify_cls = MagicMock(return_value=shopify)
    monkeypatch.setattr("integrations.shopify_service.ShopifyService", shopify_cls)

    result = await svc.execute_tool("local-tools", "get_inventory_levels", {}, {"user_id": "u"})

    assert result == [{"id": 1}]
    shopify.get_inventory_levels.assert_awaited_once()


@pytest.mark.asyncio
async def test_search_formulas_passes_workspace_id(svc, monkeypatch):
    manager = MagicMock()
    manager.search_formulas = MagicMock(return_value=[{"f": 1}])
    getter = MagicMock(return_value=manager)
    monkeypatch.setattr("core.formula_memory.get_formula_manager", getter)

    result = await svc.execute_tool(
        "local-tools",
        "search_formulas",
        {"query": "avg", "domain": "sales"},
        {"workspace_id": "ws-9", "user_id": "u"},
    )

    assert result == {"results": [{"f": 1}]}
    assert getter.call_args.kwargs.get("workspace_id") == "ws-9"
