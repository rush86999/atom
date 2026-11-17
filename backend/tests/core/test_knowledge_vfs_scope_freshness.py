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


# ---------------------------------------------------------------------------
# Follow-up: authoritative SQL tombstone vs. a still-fresh vector mirror
# ---------------------------------------------------------------------------

def _add_default_workspace(world) -> None:
    """The defect reproduction used the real default workspace id."""
    from core.models import Workspace

    world.session.add(Workspace(
        id="default", tenant_id=world.tenant_id, name="Default"))
    world.session.commit()


def _mark_sql_freshness(world, doc_id: str, status: str) -> None:
    """Mark freshness in an INDEPENDENT SQL session, as a peer worker would.

    No vector cleanup and no VFS cache invalidation happen here on purpose:
    the read path itself must consult the durable SQL tombstone.
    """
    from core.models import IngestedDocument

    other = world.Session()
    try:
        row = other.get(IngestedDocument, doc_id)
        assert row is not None
        row.freshness_status = status
        other.commit()
    finally:
        other.close()


async def _add_vector(handler, doc_id: str, text: str, *,
                      freshness="fresh", metadata=None) -> None:
    import asyncio

    extra = {}
    if freshness is not ...:
        extra["freshness_status"] = freshness
    assert await asyncio.to_thread(
        handler.add_document,
        table_name="documents",
        text=text,
        source="upload:scope.csv",
        metadata=metadata or {"file_name": f"{doc_id}.csv", "file_type": "csv"},
        user_id="user-1",
        workspace_id=handler.workspace_id,
        doc_id=doc_id,
        extra_columns=extra or None,
    ) is True


@pytest.mark.asyncio
async def test_sql_tombstone_overrides_fresh_vector_mirror_and_warm_cache(
        world, tmp_path, monkeypatch):
    """A retained SQL tombstone must deny its still-fresh LanceDB mirror.

    Reproduced independently: an ``IngestedDocument`` in workspace ``default``
    was marked ``freshness_status='removed'`` in SQL while its LanceDB row
    stayed ``fresh``. ``knowledge/documents/<id>/content.lines`` served the
    deleted text because the SQL freshness filter hid the tombstone and the
    vector fallback then resurrected the mirror. The grep cache was warmed
    first; the independent SQL update did not invalidate it.
    """
    import asyncio

    import numpy as np

    from core.embedding_service import EmbeddingService
    from core.lancedb_handler import LanceDBHandler

    async def _deterministic_embedding(self, text):
        return np.zeros(384, dtype=float).tolist()

    monkeypatch.setattr(
        EmbeddingService, "generate_embedding", _deterministic_embedding)
    _add_default_workspace(world)
    from core.models import IngestedDocument

    doc_id = "doc-sql-tombstone"
    marker = "Falcon tombstone marker 88421"
    _add_ingested(world, doc_id, "default", "short sql preview")
    handler = LanceDBHandler(
        workspace_id="default",
        db_path=str(tmp_path / "lancedb" / "default"))
    await _add_vector(handler, doc_id, f"preview\n{marker}")
    monkeypatch.setattr(
        "core.lancedb_handler.get_lancedb_handler",
        lambda ws=None, **k: handler if ws == "default" else None,
    )

    provider = _provider(world)
    ctx = {"workspace_id": "default"}

    # POSITIVE CONTROL: owner reads the fresh document through every path,
    # warming the projected-row cache used by grep.
    assert any(marker in line for line in (await provider.cat(
        "knowledge/documents/" + doc_id + "/content.lines", ctx)).lines)
    assert any(marker in line for line in (await provider.read_region(
        "knowledge/documents/" + doc_id + "/content.lines", 1, 20, ctx)).lines)
    assert await provider.grep(marker, "knowledge/documents", ctx)
    assert f"knowledge/documents/{doc_id}" in _paths(
        await provider.ls("knowledge/documents", ctx))
    assert provider._rows_cache, "grep must have warmed the projection cache"

    # A peer marks the durable SQL row removed. The vector row is untouched
    # and remains explicitly fresh; no cache invalidation is performed.
    _mark_sql_freshness(world, doc_id, "removed")
    mirror = handler.get_document_by_id("documents", doc_id)
    assert mirror is not None and marker in mirror["text"]
    assert handler.count_document_rows_by_id("documents", doc_id) == 1

    assert (await provider.cat(
        "knowledge/documents/" + doc_id + "/content.lines", ctx)).lines == []
    region = await provider.read_region(
        "knowledge/documents/" + doc_id + "/content.lines", 1, 20, ctx)
    assert region.lines == []
    assert await provider.grep(marker, "knowledge/documents", ctx) == []
    assert f"knowledge/documents/{doc_id}" not in _paths(
        await provider.ls("knowledge/documents", ctx))
    assert await provider.ls(
        f"knowledge/documents/{doc_id}", ctx) == []


@pytest.mark.asyncio
async def test_chunk_family_owner_read_and_sql_tombstone_denial(
        world, tmp_path, monkeypatch):
    """Chunk families: owner open (serialized Arrow metadata) and tombstones.

    A vector-only multi-chunk parent has no row of its own. ``_doc_meta``
    previously assumed ``metadata`` was already a dict, but the store (and
    Arrow) can hand back the serialized JSON string — so the legitimate owner
    open crashed before serving any chunk. A separate chunked document gets a
    durable SQL tombstone while all of its LanceDB chunks remain; both the
    parent id and direct ``<parent>::cN`` child reads must then be denied.
    """
    import asyncio

    import numpy as np

    from core.embedding_service import EmbeddingService
    from core.lancedb_handler import LanceDBHandler

    async def _deterministic_embedding(self, text):
        return np.zeros(384, dtype=float).tolist()

    monkeypatch.setattr(
        EmbeddingService, "generate_embedding", _deterministic_embedding)
    _add_default_workspace(world)
    _add_workspace(world, "ws-2")

    handler = LanceDBHandler(
        workspace_id="default",
        db_path=str(tmp_path / "lancedb" / "default"))
    handler_b = LanceDBHandler(
        workspace_id="ws-2", db_path=str(tmp_path / "lancedb" / "ws-2"))

    # 1) Legitimate owner chunk-parent read. No SQL mirror; metadata is stored
    #    as the serialized JSON Arrow hands back.
    parent = "chunk-vec-parent"
    await _add_vector(
        handler, f"{parent}::c1", "SECOND-CHUNK 77201",
        metadata={"file_name": "multi-chunk.xlsx", "sensitivity": "internal"})
    await _add_vector(
        handler, f"{parent}::c0", "FIRST-CHUNK 66190",
        metadata={"file_name": "multi-chunk.xlsx", "sensitivity": "internal"})

    # 2) Chunked document that will get an authoritative SQL tombstone.
    sql_chunk_parent = "chunk-sql-parent"
    _add_ingested(world, sql_chunk_parent, "default", "sql chunk preview")
    await _add_vector(
        handler, f"{sql_chunk_parent}::c0", "SQL-CHUNK-ONE 31001")
    await _add_vector(
        handler, f"{sql_chunk_parent}::c1", "SQL-CHUNK-TWO 31002")

    monkeypatch.setattr(
        "core.lancedb_handler.get_lancedb_handler",
        lambda ws=None, **k: handler if ws == "default" else (
            handler_b if ws == "ws-2" else None),
    )
    provider = _provider(world)
    ctx = {"workspace_id": "default"}
    ctx_b = {"workspace_id": "ws-2"}

    owner = await provider.cat(
        f"knowledge/documents/{parent}/content.lines", ctx)
    joined = "\n".join(owner.lines)
    assert "FIRST-CHUNK 66190" in joined and "SECOND-CHUNK 77201" in joined
    assert joined.index("FIRST-CHUNK") < joined.index("SECOND-CHUNK")
    # meta.json must not crash on the serialized metadata string.
    meta = await provider.cat(f"knowledge/documents/{parent}/meta.json", ctx)
    assert any("multi-chunk.xlsx" in line for line in meta.lines)
    assert owner.meta["file_name"] == "multi-chunk.xlsx"

    # Exact child id remains directly addressable for the owner, and the
    # peer workspace still gets nothing (scope is physical store + SQL).
    child = await provider.cat(
        f"knowledge/documents/{parent}::c0/content.lines", ctx)
    assert any("FIRST-CHUNK" in line for line in child.lines)
    assert (await provider.cat(
        f"knowledge/documents/{parent}/content.lines", ctx_b)).lines == []
    assert (await provider.cat(
        f"knowledge/documents/{parent}::c0/content.lines", ctx_b)).lines == []

    # POSITIVE before tombstone, then warm the grep cache.
    sql_owner = await provider.cat(
        f"knowledge/documents/{sql_chunk_parent}/content.lines", ctx)
    assert any("SQL-CHUNK-ONE" in line for line in sql_owner.lines)
    assert await provider.grep("SQL-CHUNK-ONE", "knowledge/documents", ctx)

    _mark_sql_freshness(world, sql_chunk_parent, "removed")
    # All chunks still exist and are explicitly fresh.
    assert handler.count_document_rows_by_prefix(
        "documents", f"{sql_chunk_parent}::") == 2

    assert (await provider.cat(
        f"knowledge/documents/{sql_chunk_parent}/content.lines", ctx)).lines == []
    assert (await provider.read_region(
        f"knowledge/documents/{sql_chunk_parent}/content.lines", 1, 20,
        ctx)).lines == []
    # Direct chunk-id reads must honor the parent's authoritative tombstone.
    assert (await provider.cat(
        f"knowledge/documents/{sql_chunk_parent}::c0/content.lines",
        ctx)).lines == []
    assert await provider.grep("SQL-CHUNK-ONE", "knowledge/documents", ctx) == []
    listed = _paths(await provider.ls("knowledge/documents", ctx))
    assert f"knowledge/documents/{sql_chunk_parent}" not in listed
    assert f"knowledge/documents/{sql_chunk_parent}::c0" not in listed


@pytest.mark.asyncio
async def test_explicit_vector_freshness_hidden_without_sql_mirror(
        world, tmp_path, monkeypatch):
    """Vector-only rows honor their own top-level freshness status.

    ``LanceDBHandler.get_document_by_id`` projects the point-lookup row down
    to id/text/source/metadata/created_at, dropping the top-level
    ``freshness_status`` column. A vector-only ``removed`` row therefore still
    cat'd as fresh. Fresh/absent legacy rows must remain readable.
    """
    import asyncio

    import numpy as np

    from core.embedding_service import EmbeddingService
    from core.lancedb_handler import LanceDBHandler

    async def _deterministic_embedding(self, text):
        return np.zeros(384, dtype=float).tolist()

    monkeypatch.setattr(
        EmbeddingService, "generate_embedding", _deterministic_embedding)
    _add_default_workspace(world)
    handler = LanceDBHandler(
        workspace_id="default",
        db_path=str(tmp_path / "lancedb" / "default"))

    removed_marker = "ORCHID-REMOVED 99441"
    fresh_marker = "ORCHID-FRESH 99442"
    legacy_marker = "ORCHID-LEGACY 99443"
    await _add_vector(handler, "vec-removed", removed_marker,
                      freshness="removed")
    await _add_vector(handler, "vec-fresh", fresh_marker, freshness="fresh")
    # No explicit status: the historical/legacy vector-only shape.
    await _add_vector(handler, "vec-legacy", legacy_marker, freshness=...)
    # A fully-removed chunk family: neither parent nor child may resurrect.
    await _add_vector(handler, "vec-removed-chunks::c0", "GONE-CHUNK 55001",
                      freshness="removed")
    await _add_vector(handler, "vec-removed-chunks::c1", "GONE-CHUNK 55002",
                      freshness="removed")

    monkeypatch.setattr(
        "core.lancedb_handler.get_lancedb_handler",
        lambda ws=None, **k: handler if ws == "default" else None,
    )
    provider = _provider(world)
    ctx = {"workspace_id": "default"}

    # Positive controls prove denial is not a blanket empty store.
    assert any(fresh_marker in line for line in (await provider.cat(
        "knowledge/documents/vec-fresh/content.lines", ctx)).lines)
    assert any(legacy_marker in line for line in (await provider.cat(
        "knowledge/documents/vec-legacy/content.lines", ctx)).lines)
    assert await provider.grep(legacy_marker, "knowledge/documents", ctx)
    listed = _paths(await provider.ls("knowledge/documents", ctx))
    assert "knowledge/documents/vec-fresh" in listed
    assert "knowledge/documents/vec-legacy" in listed

    assert (await provider.cat(
        "knowledge/documents/vec-removed/content.lines", ctx)).lines == []
    assert (await provider.read_region(
        "knowledge/documents/vec-removed/content.lines", 1, 20, ctx)).lines == []
    assert await provider.grep(removed_marker, "knowledge/documents", ctx) == []
    assert "knowledge/documents/vec-removed" not in _paths(
        await provider.ls("knowledge/documents", ctx))

    assert (await provider.cat(
        "knowledge/documents/vec-removed-chunks/content.lines", ctx)).lines == []
    assert (await provider.cat(
        "knowledge/documents/vec-removed-chunks::c0/content.lines",
        ctx)).lines == []
    assert await provider.grep("GONE-CHUNK", "knowledge/documents", ctx) == []
    listed = _paths(await provider.ls("knowledge/documents", ctx))
    assert "knowledge/documents/vec-removed-chunks" not in listed
    assert "knowledge/documents/vec-removed-chunks::c0" not in listed

    # The denied rows still exist: this is visibility, not deletion.
    assert handler.count_document_rows_by_id("documents", "vec-removed") == 1
    assert handler.count_document_rows_by_prefix(
        "documents", "vec-removed-chunks::") == 2
    assert removed_marker in handler.get_document_by_id(
        "documents", "vec-removed")["text"]


@pytest.mark.asyncio
async def test_unreadable_sql_state_fails_closed_for_vector_reads(
        world, tmp_path, monkeypatch):
    """If the authoritative SQL store cannot be read, do not serve vectors.

    Tombstones are durable SQL rows the vector store may not reflect, so an
    unreadable SQL state is not evidence that a document is current.
    """
    import asyncio

    import numpy as np

    from core.embedding_service import EmbeddingService
    from core.lancedb_handler import LanceDBHandler

    async def _deterministic_embedding(self, text):
        return np.zeros(384, dtype=float).tolist()

    monkeypatch.setattr(
        EmbeddingService, "generate_embedding", _deterministic_embedding)
    marker = "UNKNOWN-SQL-STATE 12321"
    handler = LanceDBHandler(
        workspace_id="default",
        db_path=str(tmp_path / "lancedb" / "default"))
    await _add_vector(handler, "vec-unreadable-sql", marker)
    monkeypatch.setattr(
        "core.lancedb_handler.get_lancedb_handler",
        lambda ws=None, **k: handler if ws == "default" else None,
    )

    from integrations.vfs.knowledge_vfs import KnowledgeVFSProvider

    def _broken_db():
        raise RuntimeError("SQL store unavailable")

    provider = KnowledgeVFSProvider(db_factory=_broken_db)
    ctx = {"workspace_id": "default"}

    assert (await provider.cat(
        "knowledge/documents/vec-unreadable-sql/content.lines",
        ctx)).lines == []
    assert await provider.grep(marker, "knowledge/documents", ctx) == []
    assert _paths(await provider.ls("knowledge/documents", ctx)) == set()
