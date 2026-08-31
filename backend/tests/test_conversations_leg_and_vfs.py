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
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
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
async def test_vfs_grep_root_includes_conversations(monkeypatch):
    """Root grep scans BOTH stores via the batched path and merges hits."""
    import io

    import pyarrow as pa

    from integrations.vfs.knowledge_vfs import KnowledgeVFSProvider

    class FakeCommsTable:
        def head(self, n):
            return pa.table({
                "id": pa.array(["c1"]),
                "content": pa.array(["we need the quote by Friday"]),
            }).slice(0, n)

        def to_arrow(self):
            return self.head(200)

    v = KnowledgeVFSProvider()
    monkeypatch.setattr(v, "_comms_table", lambda: FakeCommsTable())

    class FakeDocTable:
        def to_arrow(self):
            return pa.table({"id": pa.array([], pa.string()), "text": pa.array([], pa.string())})

    class FakeHandler:
        def get_table(self, name):
            return FakeDocTable()

    monkeypatch.setattr(
        "core.lancedb_handler.get_lancedb_handler", lambda *a, **k: FakeHandler()
    )

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from core.database import Base

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    v._db_factory = lambda: Session(bind=engine)

    hits = await v.grep("Friday", "/")

    assert len(hits) == 1 and "Friday" in hits[0].snippet
    assert hits[0].path == "knowledge/conversations/c1"
