# -*- coding: utf-8 -*-
"""Documents search workspace scope — uploads must be visible to chat.

Found during the Phase E cloud loop: the browser uploaded a document through
the Documents UI (and the ingestion route) into the caller's per-workspace
LanceDB store, but the chat's ``documents.search`` vector leg opened the BASE
``atom_memory`` store (hardcoded ``get_lancedb_handler("default")``), so the
grounded turn answered "couldn't find any matching lines" with the document
sitting in the durable store. The lexical leg was similarly unscoped.

Contract pinned here:

* ``DocumentsHybridSearch(workspace_id=...)`` reads the workspace's own store
  in the vector leg (and passes the workspace to the lexical leg);
* the ``documents.search`` action resolves the workspace from the dispatch
  context, else the turn's published request scope — and passes it through;
* the legacy (flag-off) path filters both stores to the caller's workspace
  (knowledge rows may be unscoped/NULL, never another workspace's).
"""
import os

os.environ.setdefault("TESTING", "1")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_vector_leg_uses_the_workspace_handler(monkeypatch):
    from core.hybrid_search import documents_hybrid as dh

    captured = {}

    def _fake_get_handler(workspace_id=None, **kwargs):
        captured["workspace_id"] = workspace_id
        handler = MagicMock()
        handler.search.return_value = [{"id": "doc_1", "_distance": 0.1}]
        return handler

    monkeypatch.setattr(
        "core.lancedb_handler.get_lancedb_handler", _fake_get_handler)
    monkeypatch.setattr(dh, "_vector_leg_enabled", lambda: True)

    svc = dh.DocumentsHybridSearch(workspace_id="ws-42")
    rows = await svc._vector_leg("zephyr launch code", limit=5)
    assert captured["workspace_id"] == "ws-42"
    assert rows and rows[0]["id"] == "doc_1"


@pytest.mark.asyncio
async def test_documents_search_action_passes_context_workspace(monkeypatch):
    from core import action_registry as ar

    seen = {}

    class _SpySearch:
        def __init__(self, **kwargs):
            seen.update(kwargs)

        async def search(self, **kwargs):
            return {"success": True, "results": [], "hybrid": "lexical_only"}

    monkeypatch.setattr(
        "core.knowledge_vfs_config.knowledge_vfs_enabled", lambda: True)
    with patch("core.hybrid_search.documents_hybrid.DocumentsHybridSearch",
               _SpySearch):
        result = await ar._documents_search(
            {"query": "zephyr"}, {"workspace_id": "ws-ctx"})
    assert result["success"] is True
    assert seen.get("workspace_id") == "ws-ctx"


@pytest.mark.asyncio
async def test_documents_search_falls_back_to_request_scope(monkeypatch):
    from core import action_registry as ar
    from core.request_scope import reset_request_scope, set_request_scope

    seen = {}

    class _SpySearch:
        def __init__(self, **kwargs):
            seen.update(kwargs)

        async def search(self, **kwargs):
            return {"success": True, "results": [], "hybrid": "lexical_only"}

    monkeypatch.setattr(
        "core.knowledge_vfs_config.knowledge_vfs_enabled", lambda: True)
    token = set_request_scope("ws-scope", "t1")
    try:
        with patch("core.hybrid_search.documents_hybrid.DocumentsHybridSearch",
                   _SpySearch):
            await ar._documents_search({"query": "zephyr"}, {})
    finally:
        reset_request_scope(token)
    assert seen.get("workspace_id") == "ws-scope"


@pytest.mark.asyncio
@pytest.mark.parametrize("case", [
    "missing_principal",
    "fail_closed",
    "no_proven_workspace",
    "resolution_error",
])
async def test_zero_match_grep_unproven_authority_never_dispatches_hybrid(
    monkeypatch, case,
):
    """Regression: without an authenticated/proven document scope the planner
    must not dispatch the hybrid search at all, and must not turn the zero VFS
    grep into an absence claim. A requested workspace is never a fallback."""
    from types import SimpleNamespace

    from core import chat_tool_planner as ctp
    from core.action_registry import action_registry as ar

    plan = SimpleNamespace(
        service="documents", intent="search", use_tool=True,
        query="Search my documents for the Zephyr launch code")

    calls = []
    resolver_calls = []
    hybrid_calls = []

    async def fake_execute(name, args, context):
        calls.append(name)
        if name == "documents.grep":
            return {"success": True, "pattern": "zephyr", "matches": []}
        if name == "documents.ls":
            return {"success": True, "entries": []}
        if name == "documents.search":
            raise AssertionError(
                "hybrid search must not dispatch without proven authority")
        raise AssertionError(f"unexpected action {name}")

    class _ForbiddenHybrid:
        def __init__(self, **kwargs):
            hybrid_calls.append(("init", kwargs))

        async def search(self, **kwargs):
            hybrid_calls.append(("search", kwargs))
            return {"status": "success", "results": []}

    def fake_scope(user_id, requested_workspace_id=None):
        resolver_calls.append((user_id, requested_workspace_id))
        if case == "resolution_error":
            raise RuntimeError("database unavailable")
        if case == "no_proven_workspace":
            return {
                "workspace_id": None,
                "legacy_authority": None,
                "fail_closed": False,
            }
        # A fail-closed scope is final; the requested workspace may even be
        # echoed here and still must not become a search scope.
        return {
            "workspace_id": "ws-requested",
            "legacy_authority": None,
            "fail_closed": True,
        }

    user_id = None if case == "missing_principal" else "user-1"

    monkeypatch.setattr(
        "core.knowledge_vfs_config.knowledge_vfs_enabled", lambda: True)
    monkeypatch.setattr(ctp, "_document_scope_for_user", fake_scope)
    monkeypatch.setattr(ar, "execute_action", fake_execute)
    monkeypatch.setattr(
        "core.hybrid_search.documents_hybrid.DocumentsHybridSearch",
        _ForbiddenHybrid)

    block = await ctp._documents_vfs_block(
        plan, user_id, {"workspace_id": "ws-requested"})

    assert hybrid_calls == []
    assert "documents.search" not in calls
    assert block and "unavailable" in block
    assert "NOT established" in block
    assert "none in the VFS" not in block
    if case == "missing_principal":
        assert resolver_calls == []
    receipt = (getattr(plan, "_result_meta", {}) or {}).get(
        "documents_read") or {}
    assert receipt.get("executed") is False


@pytest.mark.asyncio
async def test_zero_match_grep_falls_back_to_hybrid_search(monkeypatch):
    """A source-ask that greps the VFS to zero matches must consult the
    ingested-documents hybrid search before concluding nothing exists."""
    from types import SimpleNamespace

    from core import chat_tool_planner as ctp
    from core.action_registry import action_registry as ar

    plan = SimpleNamespace(
        service="documents", intent="search", use_tool=True,
        query="Search my documents for the Zephyr launch code")

    calls = []
    hybrid_init = []
    hybrid_search = []

    async def fake_execute(name, args, context):
        calls.append((name, args, context))
        if name == "documents.grep":
            return {"success": True, "pattern": "zephyr", "matches": []}
        raise AssertionError(f"unexpected action {name}")

    class _SpyHybrid:
        def __init__(self, **kwargs):
            hybrid_init.append(kwargs)

        async def search(self, **kwargs):
            hybrid_search.append(kwargs)
            return {
                "success": True,
                "status": "success",
                "results": [{
                    "source": "ingested", "id": "doc_1",
                    "title": "zephyr_notes.md",
                    "preview": "Marker: ZEPHYR-9",
                    "content": "Project Zephyr-9 launch planning. The launch "
                               "code for project Zephyr-9 is QUARTZ-77."}],
                "legs": {"lexical": {"status": "ok", "required": True}},
                "coverage": {"unavailable": []},
            }

    def fake_scope(user_id, requested_workspace_id=None):
        assert user_id == "u-1"
        assert requested_workspace_id == "ws-1"
        return {
            "workspace_id": "doc-ws",
            "legacy_authority": None,
            "fail_closed": False,
        }

    monkeypatch.setattr(
        "core.knowledge_vfs_config.knowledge_vfs_enabled", lambda: True)
    monkeypatch.setattr(ctp, "_document_scope_for_user", fake_scope)
    monkeypatch.setattr(ar, "execute_action", fake_execute)
    monkeypatch.setattr(
        "core.hybrid_search.documents_hybrid.DocumentsHybridSearch",
        _SpyHybrid)

    block = await ctp._documents_vfs_block(plan, "u-1", {"workspace_id": "ws-1"})
    assert block and "QUARTZ-77" in block
    assert "documents.search" not in [c[0] for c in calls]
    # The resolver's proven workspace is the ONLY scope the retriever gets;
    # the raw requested workspace is never forwarded.
    assert hybrid_init == [{"workspace_id": "doc-ws"}]
    assert hybrid_search == [{
        "query": "Search my documents for the Zephyr launch code",
        "limit": 6,
        "owner_user_id": "u-1",
    }]
    receipt = (getattr(plan, "_result_meta", {}) or {}).get("documents_read") or {}
    assert receipt.get("executed") is True
    assert receipt.get("match_count") == 1
    assert receipt.get("workspace_id") == "doc-ws"


@pytest.mark.asyncio
async def test_zero_match_grep_uses_trusted_principal_scope(monkeypatch):
    """The ingested-document fallback uses the persisted-principal proof: the
    server-resolved user_id yields the authorized document workspace, not the
    requested workspace, and the supported leading uploaded-only qualifier is
    carried as the compatible search filter."""
    from types import SimpleNamespace

    from core import chat_tool_planner as ctp
    from core.action_registry import action_registry as ar

    query = (
        "Using my uploaded documentation only, what is the reference code "
        "for car crash coverage?"
    )
    plan = SimpleNamespace(
        service="documents", intent="search", use_tool=True, query=query)

    calls = []
    hybrid_init = []
    hybrid_search = []

    async def fake_execute(name, args, context):
        calls.append((name, args, context))
        if name == "documents.grep":
            return {"success": True, "pattern": query, "matches": []}
        raise AssertionError(f"unexpected action {name}")

    class _SpyHybrid:
        def __init__(self, **kwargs):
            hybrid_init.append(kwargs)

        async def search(self, **kwargs):
            hybrid_search.append(kwargs)
            return {
                "success": True,
                "status": "success",
                "results": [{
                    "source": "ingested", "id": "doc-1",
                    "title": "fleet_coverage_2026.pdf",
                    "content": "Car crash coverage reference code: MV-2271.",
                }],
                "legs": {
                    "lexical": {"status": "ok", "required": True},
                    "vector": {"status": "ok", "required": True},
                    "vector_legacy": {"status": "ok", "required": False},
                },
                "coverage": {"unavailable": []},
            }

    def fake_scope(user_id, requested_workspace_id=None):
        assert user_id == "user-1"
        assert requested_workspace_id == "ws-requested"
        return {
            "workspace_id": "doc-ws",
            "legacy_authority": {
                "workspace_id": "doc-ws", "user_id": "user-1"},
            "fail_closed": False,
        }

    monkeypatch.setattr(
        "core.knowledge_vfs_config.knowledge_vfs_enabled", lambda: True)
    monkeypatch.setattr(ctp, "_document_scope_for_user", fake_scope)
    monkeypatch.setattr(ar, "execute_action", fake_execute)
    monkeypatch.setattr(
        "core.hybrid_search.documents_hybrid.DocumentsHybridSearch",
        _SpyHybrid)

    block = await ctp._documents_vfs_block(
        plan, "user-1", {"workspace_id": "ws-requested"})

    assert block and "MV-2271" in block
    assert "documents.search" not in [c[0] for c in calls]
    # EXACT assembler construction: the resolver's proven workspace AND the
    # proven legacy authority both reach the retriever.
    assert hybrid_init == [{
        "workspace_id": "doc-ws",
        "legacy_authority": {
            "workspace_id": "doc-ws", "user_id": "user-1"},
    }]
    assert len(hybrid_search) == 1
    search_call = hybrid_search[0]
    assert search_call["source"] == "ingested"
    assert len(search_call["query"]) <= ctp._DOCUMENTS_SEARCH_QUERY_CHAR_CAP
    assert search_call["limit"] == 6
    # The server owner boundary travels as the search's owner_user_id, not
    # as a workspace fallback.
    assert search_call["owner_user_id"] == "user-1"
    receipt = (getattr(plan, "_result_meta", {}) or {}).get(
        "documents_read") or {}
    assert receipt.get("executed") is True
    assert receipt.get("match_count") == 1


@pytest.mark.asyncio
async def test_zero_match_grep_scoped_absence(monkeypatch):
    """A completed zero-result scoped search plus a zero VFS grep may state a
    scoped absence, never a global one."""
    from types import SimpleNamespace

    from core import chat_tool_planner as ctp
    from core.action_registry import action_registry as ar

    plan = SimpleNamespace(
        service="documents", intent="search", use_tool=True,
        query="Search my documents for the Zephyr launch code")

    hybrid_search = []

    async def fake_execute(name, args, context):
        if name == "documents.grep":
            return {"success": True, "pattern": "zephyr", "matches": []}
        if name == "documents.ls":
            return {"success": True, "entries": []}
        raise AssertionError(f"unexpected action {name}")

    class _ZeroHybrid:
        def __init__(self, **kwargs):
            pass

        async def search(self, **kwargs):
            hybrid_search.append(kwargs)
            return {
                "success": True,
                "status": "success",
                "results": [],
                "legs": {
                    "lexical": {"status": "ok", "required": True},
                    "vector": {"status": "ok", "required": True},
                },
                "coverage": {"unavailable": []},
            }

    def fake_scope(user_id, requested_workspace_id=None):
        return {
            "workspace_id": "doc-ws",
            "legacy_authority": None,
            "fail_closed": False,
        }

    monkeypatch.setattr(
        "core.knowledge_vfs_config.knowledge_vfs_enabled", lambda: True)
    monkeypatch.setattr(ctp, "_document_scope_for_user", fake_scope)
    monkeypatch.setattr(ar, "execute_action", fake_execute)
    monkeypatch.setattr(
        "core.hybrid_search.documents_hybrid.DocumentsHybridSearch",
        _ZeroHybrid)

    block = await ctp._documents_vfs_block(
        plan, "user-1", {"workspace_id": "ws-requested"})

    assert block and "none in the VFS" in block
    assert "completed with no matching result" in block
    assert "scoped to those two searches" in block
    assert "NOT established" not in block
    assert "unavailable" not in block
    # No standalone question exists in this request, so the bounded probe
    # must not add a second lookup.
    assert len(hybrid_search) == 1
    receipt = (getattr(plan, "_result_meta", {}) or {}).get(
        "documents_read") or {}
    assert receipt.get("executed") is True
    assert receipt.get("match_count") == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["failed", "partial"])
async def test_zero_match_grep_incomplete_coverage_does_not_claim_absence(
        monkeypatch, status):
    """A partial/failed ingested-document search is reported as an unavailable
    lookup, never a completed zero; the zero VFS grep stays scoped and cannot
    become "nothing exists"."""
    from types import SimpleNamespace

    from core import chat_tool_planner as ctp
    from core.action_registry import action_registry as ar

    plan = SimpleNamespace(
        service="documents", intent="search", use_tool=True,
        query="Search my documents for the Zephyr launch code")

    async def fake_execute(name, args, context):
        if name == "documents.grep":
            return {"success": True, "pattern": "zephyr", "matches": []}
        if name == "documents.ls":
            return {"success": True, "entries": []}
        raise AssertionError(f"unexpected action {name}")

    class _BrokenHybrid:
        def __init__(self, **kwargs):
            pass

        async def search(self, **kwargs):
            return {
                "success": status != "failed",
                "status": status,
                "results": [],
                "legs": {
                    "lexical": {
                        "status": "failed", "required": True,
                        "error_category": "source_unavailable"},
                    "vector": {"status": "ok", "required": False},
                },
                "coverage": {"unavailable": ["lexical"]},
            }

    def fake_scope(user_id, requested_workspace_id=None):
        return {
            "workspace_id": "doc-ws",
            "legacy_authority": None,
            "fail_closed": False,
        }

    monkeypatch.setattr(
        "core.knowledge_vfs_config.knowledge_vfs_enabled", lambda: True)
    monkeypatch.setattr(ctp, "_document_scope_for_user", fake_scope)
    monkeypatch.setattr(ar, "execute_action", fake_execute)
    monkeypatch.setattr(
        "core.hybrid_search.documents_hybrid.DocumentsHybridSearch",
        _BrokenHybrid)

    block = await ctp._documents_vfs_block(
        plan, "user-1", {"workspace_id": "ws-requested"})

    assert block and "document search coverage" in block
    assert "unavailable: lexical" in block
    assert "unavailable" in block
    assert "NOT established" in block
    assert "none in the VFS" not in block
    receipt = (getattr(plan, "_result_meta", {}) or {}).get(
        "documents_read") or {}
    assert receipt.get("executed") is False
    assert "document search coverage" in receipt.get("error")


@pytest.mark.asyncio
async def test_zero_match_grep_retries_only_a_complete_zero(monkeypatch):
    """The bounded probe runs on a completed zero with an exact standalone
    question, reusing the SAME scope/limit/owner search flags."""
    from types import SimpleNamespace

    from core import chat_tool_planner as ctp
    from core.action_registry import action_registry as ar

    query = "Please check the notes. What is the Zephyr launch code?"
    plan = SimpleNamespace(
        service="documents", intent="search", use_tool=True, query=query)

    hybrid_init = []
    hybrid_search = []

    async def fake_execute(name, args, context):
        if name == "documents.grep":
            return {"success": True, "pattern": "zephyr", "matches": []}
        raise AssertionError(f"unexpected action {name}")

    class _RetryHybrid:
        def __init__(self, **kwargs):
            hybrid_init.append(kwargs)

        async def search(self, **kwargs):
            hybrid_search.append(kwargs)
            if len(hybrid_search) == 1:
                return {
                    "success": True,
                    "status": "success",
                    "results": [],
                    "legs": {"lexical": {"status": "ok", "required": True}},
                    "coverage": {"unavailable": []},
                }
            return {
                "success": True,
                "status": "success",
                "results": [{
                    "source": "ingested", "id": "doc-2",
                    "title": "zephyr_notes.md",
                    "content": "The Zephyr launch code is QUARTZ-77.",
                }],
                "legs": {"lexical": {"status": "ok", "required": True}},
                "coverage": {"unavailable": []},
            }

    def fake_scope(user_id, requested_workspace_id=None):
        return {
            "workspace_id": "doc-ws",
            "legacy_authority": {"workspace_id": "doc-ws"},
            "fail_closed": False,
        }

    monkeypatch.setattr(
        "core.knowledge_vfs_config.knowledge_vfs_enabled", lambda: True)
    monkeypatch.setattr(ctp, "_document_scope_for_user", fake_scope)
    monkeypatch.setattr(ar, "execute_action", fake_execute)
    monkeypatch.setattr(
        "core.hybrid_search.documents_hybrid.DocumentsHybridSearch",
        _RetryHybrid)

    block = await ctp._documents_vfs_block(
        plan, "user-1", {"workspace_id": "ws-requested"})

    assert block and "QUARTZ-77" in block
    assert len(hybrid_init) == 1
    assert hybrid_init[0] == {
        "workspace_id": "doc-ws",
        "legacy_authority": {"workspace_id": "doc-ws"},
    }
    assert len(hybrid_search) == 2
    assert hybrid_search[0] == {
        "query": query, "limit": 6, "owner_user_id": "user-1"}
    assert hybrid_search[1] == {
        "query": "What is the Zephyr launch code?",
        "limit": 6, "owner_user_id": "user-1"}
    receipt = (getattr(plan, "_result_meta", {}) or {}).get(
        "documents_read") or {}
    assert receipt.get("executed") is True
    assert receipt.get("match_count") == 1
    assert receipt.get("workspace_id") == "doc-ws"


@pytest.mark.asyncio
async def test_legacy_path_filters_to_the_workspace(monkeypatch):
    from core import action_registry as ar

    ingested_q = MagicMock()
    ingested_q.all.return_value = []
    ingested_q.limit.return_value = ingested_q
    ingested_q.filter.return_value = ingested_q
    knowledge_q = MagicMock()
    knowledge_q.all.return_value = []
    knowledge_q.limit.return_value = knowledge_q
    knowledge_q.filter.return_value = knowledge_q

    db = MagicMock()
    db.query.side_effect = [ingested_q, knowledge_q]
    ctx_manager = MagicMock()
    ctx_manager.return_value.__enter__.return_value = db
    ctx_manager.return_value.__exit__.return_value = False

    monkeypatch.setattr(
        "core.knowledge_vfs_config.knowledge_vfs_enabled", lambda: False)
    with patch("core.database.get_db_session", ctx_manager):
        result = await ar._documents_search(
            {"query": "zephyr"}, {"workspace_id": "ws-legacy"})
    assert result["success"] is True
    # Base filter + workspace filter on each store.
    assert ingested_q.filter.call_count == 2
    assert knowledge_q.filter.call_count == 2


def test_upload_route_resolves_the_fk_first():
    """Documents-UI uploads must land in the user's FK workspace store — the
    relationship is empty for product-registered users, and relationship-only
    resolution wrote to default_shared while search read the user's store."""
    from types import SimpleNamespace

    from api.document_routes import _resolve_ws_id

    fk_user = SimpleNamespace(workspace_id="ws-fk", workspaces=[])
    assert _resolve_ws_id(fk_user) == "ws-fk"
    rel_user = SimpleNamespace(
        workspace_id=None, workspaces=[SimpleNamespace(id="ws-rel")])
    assert _resolve_ws_id(rel_user) == "ws-rel"
    assert _resolve_ws_id(None) is None


@pytest.mark.asyncio
async def test_upsert_document_forwards_the_freshness_stamp(monkeypatch):
    """Without freshness_status=='fresh' the search filter hides the row."""
    from api import document_routes as dr

    captured = {}

    async def fake_upsert(handler, **kwargs):
        captured.update(kwargs)
        return "written"

    monkeypatch.setattr("core.vector_upsert.upsert_document", fake_upsert)
    result = await dr._upsert_document(
        MagicMock(), text="body", doc_key="doc_1", source="upload:f.md",
        metadata={}, user_id="u-1", workspace_id="ws-1",
        extra_columns={"freshness_status": "fresh"},
    )
    assert result == "written"
    assert captured["extra_columns"] == {"freshness_status": "fresh"}
    assert captured["workspace_id"] == "ws-1"
