"""Agent awareness of the Knowledge VFS.

The VFS can be perfectly populated and still useless if agents never learn it
exists. These tests pin the three awareness surfaces (Aug 2026 journey trace):

1. CORE_TOOLS: documents.search/ls/cat/grep are attached to every
   unrestricted agent's tool list — no discovery step required.
2. Inventory context: when ingested documents exist, the memory-context
   inventory names them AND teaches the VFS calls that browse them.
3. Discovery: mcp_tool_search results carry parameter schemas so lazily
   discovered tools are callable without guesswork.
"""
import asyncio
from unittest.mock import AsyncMock

import pytest


# ---------------------------------------------------------------------------
# 1. Core tool attachment
# ---------------------------------------------------------------------------
def test_core_tools_include_knowledge_vfs_actions():
    from core.generic_agent import GenericAgent

    for tool in ("documents.search", "documents.ls", "documents.cat", "documents.grep"):
        assert tool in GenericAgent.CORE_TOOLS_NAMES, (
            f"{tool} must be a core tool: with the default allowed_tools='*' "
            "the loop attaches ONLY core tools, so anything missing here is "
            "invisible to agents unless they happen to tool-search for it"
        )


def test_registry_defines_core_vfs_actions():
    """The core list must match real registrations (typo = silently missing).

    Only the dotted registry actions are checked here — the other CORE tools
    (save_business_fact, mcp_tool_search, …) are MCP-handler tools resolved
    by name at dispatch, not action_registry entries.
    """
    from core.action_registry import action_registry
    from core.generic_agent import GenericAgent

    dotted = [t for t in GenericAgent.CORE_TOOLS_NAMES if "." in t]
    assert dotted, "expected at least the documents.* core tools"
    for tool in dotted:
        assert action_registry.get_action(tool) is not None, tool


# ---------------------------------------------------------------------------
# 2. Inventory context teaches the VFS
# ---------------------------------------------------------------------------
class _FakeTable:
    def __init__(self, rows: int):
        self._rows = rows

    def count_rows(self) -> int:
        return self._rows


class _FakeLanceDB:
    def __init__(self, tables):
        self._tables = tables

    def table_names(self):
        return list(self._tables)

    def open_table(self, name):
        return self._tables[name]


class _FakeHandler:
    def __init__(self, tables):
        self.db = _FakeLanceDB(tables)


@pytest.mark.asyncio
async def test_inventory_names_documents_and_teaches_vfs(monkeypatch):
    import core.memory_context_assembler as mca

    fake = _FakeHandler({"documents": _FakeTable(70)})

    import core.hybrid_data_ingestion as hdi

    monkeypatch.setattr(
        hdi, "get_hybrid_ingestion_service", lambda ws: type("S", (), {"memory_handler": fake})()
    )

    text = await mca._inventory_leg("default")
    assert text is not None
    assert "documents (ingested files): 70" in text
    assert "documents.ls('knowledge/documents')" in text
    assert "documents.cat('knowledge/documents/<id>/content.lines')" in text
    assert "documents.grep(pattern, 'knowledge')" in text


@pytest.mark.asyncio
async def test_inventory_stays_quiet_with_no_documents(monkeypatch):
    import core.memory_context_assembler as mca

    fake = _FakeHandler({"documents": _FakeTable(0)})

    import core.hybrid_data_ingestion as hdi

    monkeypatch.setattr(
        hdi, "get_hybrid_ingestion_service", lambda ws: type("S", (), {"memory_handler": fake})()
    )

    text = await mca._inventory_leg("default")
    assert text is None, "no documents → no inventory line (and no stale hint)"


# ---------------------------------------------------------------------------
# 3. Tool discovery keeps parameters
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_tools_results_carry_parameters():
    from integrations.mcp_service import MCPService

    svc = object.__new__(MCPService)
    svc.get_all_tools = AsyncMock(return_value=[
        {
            "name": "documents.cat",
            "description": "Read a document's FULL text as line-numbered lines",
            "parameters": {"path": "string"},
        },
        {"name": "other", "description": "read a document-ish thing", "parameters": {}},
    ])

    res = await MCPService.search_tools(svc, "document")

    hit = next(m for m in res if m["name"] == "documents.cat")
    assert hit["parameters"] == {"path": "string"}, (
        "discovered tools must carry their parameter schema — the agent "
        "lazy-loads search results as callable tools"
    )
