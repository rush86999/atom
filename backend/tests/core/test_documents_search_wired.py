"""
Hybrid search Step 4 — documents.search action wired to DocumentsHybridSearch.

Verifies the agent-facing action returns real hybrid results (bm25_vector_rrf)
when both legs fire, degrades correctly (lexical_only / no_results), and keeps
flag-off parity (legacy ILIKE, no 'hybrid' key).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_search_returns_hybrid_label_when_service_fires(monkeypatch):
    """Flag ON + service returns results → label is bm25_vector_rrf (not lexical_ranked)."""
    monkeypatch.setenv("ATOM_KNOWLEDGE_VFS_ENABLED", "true")
    from core.action_registry import action_registry

    fake_resp = {
        "success": True, "query": "revenue", "hybrid": "bm25_vector_rrf",
        "results": [{"source": "ingested", "id": "doc_1", "title": "R", "preview": "...", "score": 0.03, "bridged": True}],
        "stats": {"lexical_hits": 1, "vector_hits": 1, "unbridged_hits": 0},
    }
    with patch("core.hybrid_search.documents_hybrid.DocumentsHybridSearch") as DhsCls:
        instance = DhsCls.return_value
        instance.search = AsyncMock(return_value=fake_resp)
        res = await action_registry.execute_action(
            "documents.search", {"query": "revenue growth"}, {}
        )
    assert res["success"] is True
    assert res["hybrid"] == "bm25_vector_rrf", (
        "documents.search must return bm25_vector_rrf when the hybrid service fires, "
        "not the old 'lexical_ranked' label"
    )
    assert res["results"][0]["id"] == "doc_1"


@pytest.mark.asyncio
async def test_search_flag_off_is_legacy_parity(monkeypatch):
    """Flag OFF → exact legacy contract: no 'hybrid' key."""
    monkeypatch.setenv("ATOM_KNOWLEDGE_VFS_ENABLED", "false")
    from core.action_registry import action_registry
    res = await action_registry.execute_action(
        "documents.search", {"query": "revenue"}, {}
    )
    assert res["success"] is True
    assert "hybrid" not in res, "flag-off must be the exact legacy contract (no hybrid key)"


@pytest.mark.asyncio
async def test_search_degrades_to_no_results(monkeypatch):
    """Both legs empty → no_results label, empty results."""
    monkeypatch.setenv("ATOM_KNOWLEDGE_VFS_ENABLED", "true")
    from core.action_registry import action_registry
    fake_resp = {
        "success": True, "query": "obscure", "hybrid": "no_results",
        "results": [], "stats": {},
    }
    with patch("core.hybrid_search.documents_hybrid.DocumentsHybridSearch") as DhsCls:
        instance = DhsCls.return_value
        instance.search = AsyncMock(return_value=fake_resp)
        res = await action_registry.execute_action(
            "documents.search", {"query": "obscure xyzzy"}, {}
        )
    assert res["hybrid"] == "no_results"
    assert res["results"] == []
