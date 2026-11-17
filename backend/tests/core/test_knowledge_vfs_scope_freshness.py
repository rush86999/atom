"""Knowledge VFS and document search must honor scope, freshness, and cache.

Regression for defects reproduced 2026-11-16 on main ``0e9b0dfc9``:

1. ``POST /api/rpc/documents.cat`` for user B (a real user in a different
   workspace) returned user A's uploaded DOCX content by document id. ``ls``
   was scoped, but the point read was not — the SQL lookup had no workspace
   filter and the LanceDB fallback always opened the ``default`` store.
2. After a verified document delete, ``documents.cat``/``read_region``/``ls``/
   ``grep`` still served the retained SQL tombstone's ``content_preview``.
   Search and export already refused the removed document, so the VFS was the
   stale reference that could still ground an agent answer.
3. ``POST /api/rpc/documents.search`` searched the default store (0 hits) for
   a document the same user had just uploaded to its own workspace. The RPC
   context carries the server-owned ``User``, not a top-level workspace key,
   so the action's scope helper lost the workspace while the public search
   endpoint found the document.
4. A ``documents.grep`` before deletion warmed the VFS projected-row cache;
   after the verified delete the same grep still returned the removed text
   for the 15s TTL, so the stale reference survived the tombstone/freshness
   fix until cache invalidation was wired into the delete path.

The fixes enforce the workspace carried by the action context and the same
non-fresh statuses used by search/export, derive action scope from the
authenticated user object, and invalidate the existing projection cache after
document writes/deletes. A caller that supplies no workspace keeps the
historical default-store behavior.
"""
from __future__ import annotations

import pytest

from tests.acceptance.fixtures import world  # noqa: F401 — fixture re-export


def _add_workspace(world, workspace_id: str) -> None:
    from core.models import Workspace

    world.session.add(Workspace(
        id=workspace_id, tenant_id=world.tenant_id, name=workspace_id))
    world.session.commit()


def _add_ingested(world, doc_id: str, workspace_id: str, preview: str,
                  freshness: str = "fresh") -> None:
    from core.models import IngestedDocument

    world.session.add(IngestedDocument(
        id=doc_id,
        workspace_id=workspace_id,
        tenant_id=world.tenant_id,
        file_name=f"{doc_id}.docx",
        file_path=f"/scratch/{doc_id}.docx",
        file_type="docx",
        integration_id="manual_upload",
        external_id=f"upload_{doc_id}",
        content_preview=preview,
        freshness_status=freshness,
    ))
    world.session.commit()


def _provider(world):
    from integrations.vfs.knowledge_vfs import KnowledgeVFSProvider

    return KnowledgeVFSProvider(db_factory=world.Session)


def _paths(nodes) -> set:
    return {n.path for n in nodes}


@pytest.mark.asyncio
async def test_point_reads_respect_workspace_and_removed_status(world, monkeypatch):
    """A peer workspace cannot cat A's doc; a removed doc cannot be read."""
    # SQL-only behavior: no vector rows exist for this test.
    monkeypatch.setattr(
        "core.lancedb_handler.get_lancedb_handler", lambda *a, **k: None)
    _add_workspace(world, "ws-2")
    marker_a = "Falcon budget approved at 847,300 dollars"
    marker_b = "Tulip count is 1180 units"
    _add_ingested(world, "doc-a", "ws-1", marker_a)
    _add_ingested(world, "doc-b", "ws-2", marker_b)

    provider = _provider(world)
    ctx_a = {"workspace_id": "ws-1"}
    ctx_b = {"workspace_id": "ws-2"}

    # Owner reads its own document.
    a_cat = await provider.cat("knowledge/documents/doc-a/content.lines", ctx_a)
    assert any(marker_a in line for line in a_cat.lines)
    a_region = await provider.read_region(
        "knowledge/documents/doc-a/content.lines", 1, 10, ctx_a)
    assert any(marker_a in line for line in a_region.lines)

    # A different real workspace is denied the same id, while still reading
    # its own document (the isolation is not just an empty store).
    b_peer = await provider.cat("knowledge/documents/doc-a/content.lines", ctx_b)
    assert b_peer.lines == []
    b_own = await provider.cat("knowledge/documents/doc-b/content.lines", ctx_b)
    assert any(marker_b in line for line in b_own.lines)

    assert "knowledge/documents/doc-a" in _paths(
        await provider.ls("knowledge/documents", ctx_a))
    assert "knowledge/documents/doc-a" not in _paths(
        await provider.ls("knowledge/documents", ctx_b))
    assert "knowledge/documents/doc-b" in _paths(
        await provider.ls("knowledge/documents", ctx_b))

    a_grep = await provider.grep(marker_a, "knowledge/documents", ctx_a)
    b_grep = await provider.grep(marker_a, "knowledge/documents", ctx_b)
    assert a_grep and not b_grep

    # The delete service retains the SQL row as a tombstone (freshness
    # "removed") for receipt/replay identity. It is not source evidence.
    from core.models import IngestedDocument

    row = world.session.get(IngestedDocument, "doc-a")
    row.freshness_status = "removed"
    world.session.commit()

    assert (await provider.cat(
        "knowledge/documents/doc-a/content.lines", ctx_a)).lines == []
    assert (await provider.read_region(
        "knowledge/documents/doc-a/content.lines", 1, 10, ctx_a)).lines == []
    assert "knowledge/documents/doc-a" not in _paths(
        await provider.ls("knowledge/documents", ctx_a))
    assert await provider.grep(marker_a, "knowledge/documents", ctx_a) == []

    # A caller that supplies no workspace keeps the historical default-store
    # behavior for readable rows, but a removed document stays unreadable.
    assert (await provider.cat(
        "knowledge/documents/doc-a/content.lines", None)).lines == []


@pytest.mark.asyncio
async def test_documents_search_uses_authenticated_user_workspace(monkeypatch):
    """RPC carries the user object, not a top-level workspace key.

    Reproduced: ``POST /api/rpc/documents.search`` searched the default store
    (0 hits) for a document the same user had just uploaded to its own
    workspace; the public search endpoint found it. The action now derives the
    scope from the server-owned user object.
    """
    monkeypatch.setenv("ATOM_KNOWLEDGE_VFS_ENABLED", "true")
    calls = {}

    class _FakeHybrid:
        def __init__(self, db=None, lancedb=None, workspace_id=None):
            calls["workspace_id"] = workspace_id

        async def search(self, query, limit=10, **kwargs):
            return {
                "success": True, "query": query, "results": [],
                "hybrid": "lexical_only", "status": "success",
            }

    import core.hybrid_search.documents_hybrid as hybrid_module
    from core.action_registry import action_registry

    monkeypatch.setattr(
        hybrid_module, "DocumentsHybridSearch", _FakeHybrid)

    from types import SimpleNamespace

    result = await action_registry.execute_action(
        "documents.search", {"query": "falcon budget"},
        {"user": SimpleNamespace(workspace_id="ws-authenticated")},
    )
    assert result["success"] is True
    assert calls["workspace_id"] == "ws-authenticated"

    # An explicit, server-supplied dispatch scope still wins.
    await action_registry.execute_action(
        "documents.search", {"query": "falcon budget"},
        {"workspace_id": "ws-explicit",
         "user": SimpleNamespace(workspace_id="ws-authenticated")},
    )
    assert calls["workspace_id"] == "ws-explicit"


@pytest.mark.asyncio
async def test_vector_only_rows_are_workspace_scoped(world, tmp_path, monkeypatch):
    """The LanceDB fallback/ls/grep must use the caller's physical store."""
    import asyncio

    import numpy as np

    from core.embedding_service import EmbeddingService
    from core.lancedb_handler import LanceDBHandler

    async def _deterministic_embedding(self, text):
        return np.zeros(384, dtype=float).tolist()

    monkeypatch.setattr(
        EmbeddingService, "generate_embedding", _deterministic_embedding)

    marker_a = "Orchid units in the North region total 9241"
    handler_a = LanceDBHandler(
        workspace_id="ws-1", db_path=str(tmp_path / "lancedb" / "ws-1"))
    handler_b = LanceDBHandler(
        workspace_id="ws-2", db_path=str(tmp_path / "lancedb" / "ws-2"))
    assert await asyncio.to_thread(
        handler_a.add_document,
        table_name="documents",
        text=marker_a,
        source="upload:Orchid.csv",
        metadata={"file_name": "Orchid.csv", "file_type": "csv"},
        user_id="user-1",
        workspace_id="ws-1",
        doc_id="vec-a",
        extra_columns={"freshness_status": "fresh"},
    ) is True

    monkeypatch.setattr(
        "core.lancedb_handler.get_lancedb_handler",
        lambda ws=None, **k: handler_a if ws == "ws-1" else (
            handler_b if ws == "ws-2" else None),
    )

    provider = _provider(world)
    ctx_a = {"workspace_id": "ws-1"}
    ctx_b = {"workspace_id": "ws-2"}

    a_cat = await provider.cat("knowledge/documents/vec-a/content.lines", ctx_a)
    assert any(marker_a in line for line in a_cat.lines)
    assert (await provider.cat(
        "knowledge/documents/vec-a/content.lines", ctx_b)).lines == []

    assert "knowledge/documents/vec-a" in _paths(
        await provider.ls("knowledge/documents", ctx_a))
    assert "knowledge/documents/vec-a" not in _paths(
        await provider.ls("knowledge/documents", ctx_b))

    a_grep = await provider.grep(marker_a, "knowledge/documents", ctx_a)
    b_grep = await provider.grep(marker_a, "knowledge/documents", ctx_b)
    assert a_grep and not b_grep


@pytest.mark.asyncio
async def test_invalidation_drops_cached_removed_vector_text(
        world, tmp_path, monkeypatch):
    """A removed vector row must not survive in the VFS projection cache.

    Reproduced end-to-end: owner ``documents.grep`` before delete warmed the
    15s projected-row cache; after a verified delete the same grep still
    returned the removed document's text. The delete service now invalidates
    the registered knowledge provider's cache.
    """
    import asyncio

    import numpy as np

    from core.embedding_service import EmbeddingService
    from core.lancedb_handler import LanceDBHandler
    import core.vfs_registry as vfs_registry
    from integrations.vfs.knowledge_vfs import invalidate_knowledge_vfs_rows_cache

    async def _deterministic_embedding(self, text):
        return np.zeros(384, dtype=float).tolist()

    monkeypatch.setattr(
        EmbeddingService, "generate_embedding", _deterministic_embedding)
    marker = "Removed cache marker 55291"
    handler = LanceDBHandler(
        workspace_id="ws-cache",
        db_path=str(tmp_path / "lancedb" / "ws-cache"))
    assert await asyncio.to_thread(
        handler.add_document,
        table_name="documents",
        text=marker,
        source="upload:cache.csv",
        metadata={"file_name": "cache.csv", "file_type": "csv"},
        user_id="user-1",
        workspace_id="ws-cache",
        doc_id="vec-cache",
        extra_columns={"freshness_status": "fresh"},
    ) is True
    monkeypatch.setattr(
        "core.lancedb_handler.get_lancedb_handler",
        lambda ws=None, **k: handler if ws == "ws-cache" else None,
    )

    provider = _provider(world)
    monkeypatch.setattr(
        vfs_registry, "get_provider",
        lambda prefix: provider if prefix == "knowledge" else None,
    )
    ctx = {"workspace_id": "ws-cache"}
    assert await provider.grep(marker, "knowledge/documents", ctx)
    assert provider._rows_cache, "grep must have warmed the projection cache"

    assert handler.delete_documents_by_id("documents", "vec-cache") is True
    # Without invalidation the TTL cache still serves the removed text.
    assert await provider.grep(marker, "knowledge/documents", ctx)

    invalidate_knowledge_vfs_rows_cache()
    assert await provider.grep(marker, "knowledge/documents", ctx) == []
