"""
Conversations leg (P1.3 first slice) + Knowledge VFS conversations subtree.

The comms memory store is searched as a first-class documents.search leg
(bridge, don't copy) and exposed as knowledge/conversations/<id>/content.lines
with the same ls/cat/grep ergonomics as documents.
"""

import os
os.environ.setdefault("TESTING", "1")

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# --------------------------------------------------------------------------- #
# Conversations leg in DocumentsHybridSearch
# --------------------------------------------------------------------------- #

def _fake_comm_record(cid="c1", content="Sarah asked about the press brake deadline", app="slack"):
    return {"id": cid, "content": content, "app_type": app, "timestamp": "2026-08-19T10:00:00"}


@pytest.mark.asyncio
async def test_conversations_leg_appends_results(monkeypatch):
    monkeypatch.setenv("MEMORY_CONVERSATIONS_LEG", "true")
    from core.hybrid_search import documents_hybrid as dh

    svc = dh.DocumentsHybridSearch()

    async def fake_vector(query, limit, source=None):
        return []

    with patch.object(svc, "_lexical_leg", return_value=[]), \
         patch.object(svc, "_vector_leg", fake_vector), \
         patch.object(svc, "_conversations_leg", AsyncMock(return_value=[{
             "id": "c1", "source": "communication", "title": "slack — 2026-08-19",
             "preview": "Sarah asked…", "bridged": True, "legs": ["conversations"], "score": 0.0,
         }])):
        r = await svc.search(query="what did Sarah say about the deadline", limit=5)

    assert r.get("success") is True
    assert len(r.get("results", [])) == 1
    assert r["results"][0]["source"] == "communication"
    assert r.get("stats", {}).get("conversation_hits") == 1


@pytest.mark.asyncio
async def test_conversations_leg_disabled_by_env(monkeypatch):
    monkeypatch.setenv("MEMORY_CONVERSATIONS_LEG", "false")
    from core.hybrid_search import documents_hybrid as dh

    svc = dh.DocumentsHybridSearch()

    async def fake_vector(query, limit, source=None):
        return []

    leg = AsyncMock(return_value=[])
    with patch.object(svc, "_lexical_leg", return_value=[]), \
         patch.object(svc, "_vector_leg", fake_vector), \
         patch.object(svc, "_conversations_leg", leg):
        await svc.search(query="anything at all", limit=5)

    leg.assert_not_awaited()


@pytest.mark.asyncio
async def test_conversations_leg_skipped_with_source_filter(monkeypatch):
    monkeypatch.setenv("MEMORY_CONVERSATIONS_LEG", "true")
    from core.hybrid_search import documents_hybrid as dh

    svc = dh.DocumentsHybridSearch()

    async def fake_vector(query, limit, source=None):
        return []

    leg = AsyncMock(return_value=[])
    with patch.object(svc, "_lexical_leg", return_value=[]), \
         patch.object(svc, "_vector_leg", fake_vector), \
         patch.object(svc, "_conversations_leg", leg):
        await svc.search(query="anything at all", limit=5, source="ingested")

    leg.assert_not_awaited()


# --------------------------------------------------------------------------- #
# Knowledge VFS conversations subtree
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_vfs_lists_conversations_subtree():
    from integrations.vfs.knowledge_vfs import KnowledgeVFSProvider, VFSNode

    v = KnowledgeVFSProvider()
    with patch.object(v, "_list_conversations", AsyncMock(return_value=[
        VFSNode(name="c1", type="dir", path="knowledge/conversations/c1")
    ])):
        nodes = await v.ls("knowledge/conversations")
    assert len(nodes) == 1 and nodes[0].path == "knowledge/conversations/c1"


@pytest.mark.asyncio
async def test_vfs_cats_conversation():
    from integrations.vfs.knowledge_vfs import KnowledgeVFSProvider

    v = KnowledgeVFSProvider()
    with patch.object(v, "_get_conversation", AsyncMock(return_value={
        "id": "c1", "app_type": "telegram", "content": "we need the quote by Friday", "timestamp": "2026-08-19",
    })):
        res = await v.cat("knowledge/conversations/c1/content.lines")
    assert any("Friday" in line for line in res.lines)


@pytest.mark.asyncio
async def test_vfs_grep_root_includes_conversations():
    from integrations.vfs.knowledge_vfs import KnowledgeVFSProvider, VFSNode, VFSResource

    v = KnowledgeVFSProvider()
    doc_nodes = [VFSNode(name="d1", type="dir", path="knowledge/documents/d1")]
    conv_nodes = [VFSNode(name="c1", type="dir", path="knowledge/conversations/c1")]

    async def fake_ls(path, ctx=None):
        return doc_nodes if path == "knowledge/documents" else conv_nodes

    async def fake_cat(path, ctx=None):
        if "conversations" in path:
            return VFSResource(path=path, lines=["L1: quote due Friday"])
        return VFSResource(path=path)

    with patch.object(v, "ls", fake_ls), patch.object(v, "cat", fake_cat):
        hits = await v.grep("Friday", "/")

    assert len(hits) == 1 and "Friday" in hits[0].snippet
