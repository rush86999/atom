"""
Coverage wave 9b — core/action_registry.py VFS action family
(documents.ls/cat/grep/tree/head/tail/scan/map/reduce/ask_image,
legacy search paths, mini-app db lazy wrappers, context helpers).
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.action_registry import action_registry
from core.vfs_base import VFSCitation, VFSNode, VFSResource


def make_fake_provider():
    p = MagicMock()
    p.prefix = "knowledge"
    return p


@pytest.fixture(autouse=True)
def vfs_enabled():
    with patch("core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True):
        yield


@pytest.fixture
def provider():
    p = make_fake_provider()
    with patch("core.vfs_registry.get_provider", return_value=p), patch(
        "core.vfs_registry.resolve_provider", return_value=p
    ):
        yield p


# ============================================================================
# documents.ls / cat / grep
# ============================================================================

class TestDocumentsLs:
    @pytest.mark.asyncio
    async def test_ls_returns_entries(self, provider):
        provider.ls = AsyncMock(return_value=[
            VFSNode(name="doc1", type="dir", path="knowledge/documents/doc1"),
            VFSNode(name="meta.json", type="file", path="knowledge/documents/doc1/meta.json", size=12),
        ])
        result = await action_registry.execute_action("documents.ls", {"path": "knowledge/documents"}, {})
        assert result["success"] is True
        assert len(result["entries"]) == 2
        assert result["entries"][0]["name"] == "doc1"
        assert result["entries"][1]["size"] == 12

    @pytest.mark.asyncio
    async def test_ls_no_provider(self):
        with patch("core.vfs_registry.resolve_provider", return_value=None):
            result = await action_registry.execute_action("documents.ls", {"path": "knowledge/x"}, {})
        assert result["success"] is False
        assert result["error"] == "no_provider"

    @pytest.mark.asyncio
    async def test_ls_disabled(self):
        with patch("core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=False):
            result = await action_registry.execute_action("documents.ls", {"path": "knowledge"}, {})
        assert result["success"] is False
        assert result["error"] == "vfs_disabled"


class TestDocumentsCat:
    @pytest.mark.asyncio
    async def test_cat_returns_resource(self, provider):
        provider.cat = AsyncMock(return_value=VFSResource(
            path="knowledge/documents/d1/content.lines",
            meta={"title": "kb"},
            lines=["L1: alpha", "L2: beta"],
        ))
        result = await action_registry.execute_action("documents.cat", {"path": "knowledge/documents/d1/content.lines"}, {})
        assert result["success"] is True
        assert result["path"] == "knowledge/documents/d1/content.lines"
        assert result["line_count"] == 2
        assert result["content"] == "L1: alpha\nL2: beta"

    @pytest.mark.asyncio
    async def test_cat_no_provider(self):
        with patch("core.vfs_registry.resolve_provider", return_value=None):
            result = await action_registry.execute_action("documents.cat", {"path": "knowledge/d"}, {})
        assert result["success"] is False


class TestDocumentsGrep:
    @pytest.mark.asyncio
    async def test_grep_returns_citations(self, provider):
        provider.grep = AsyncMock(return_value=[
            VFSCitation(path="knowledge/documents/d1/content.lines", line=47, snippet="L47: alpha"),
        ])
        result = await action_registry.execute_action(
            "documents.grep", {"pattern": "alpha", "path_prefix": "knowledge/documents"}, {}
        )
        assert result["success"] is True
        assert result["matches"][0]["line"] == 47
        assert result["matches"][0]["snippet"] == "L47: alpha"

    @pytest.mark.asyncio
    async def test_grep_no_provider(self):
        with patch("core.vfs_registry.resolve_provider", return_value=None):
            result = await action_registry.execute_action(
                "documents.grep", {"pattern": "x", "path_prefix": "knowledge"}, {}
            )
        assert result["success"] is False
        assert result["error"] == "no_provider"


# ============================================================================
# documents.tree / head / tail
# ============================================================================

class TestDocumentsTree:
    @pytest.mark.asyncio
    async def test_tree_renders_dir_and_file(self, provider):
        provider.ls = AsyncMock(side_effect=[
            [VFSNode(name="d1", type="dir", path="knowledge/d1")],
            [VFSNode(name="f1", type="file", path="knowledge/d1/f1", size=5)],
        ])
        result = await action_registry.execute_action("documents.tree", {"path": "knowledge", "depth": 2}, {})
        assert result["success"] is True
        assert result["tree"][0] == "knowledge"
        assert any("d1" in line for line in result["tree"])
        assert any("f1" in line for line in result["tree"])

    @pytest.mark.asyncio
    async def test_tree_ls_failure_tolerated(self, provider):
        provider.ls = AsyncMock(side_effect=RuntimeError("ls exploded"))
        result = await action_registry.execute_action("documents.tree", {"path": "knowledge"}, {})
        assert result["success"] is True
        assert result["tree"] == ["knowledge"]

    @pytest.mark.asyncio
    async def test_tree_no_provider(self):
        with patch("core.vfs_registry.resolve_provider", return_value=None):
            result = await action_registry.execute_action("documents.tree", {"path": "knowledge"}, {})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_tree_depth_clamped(self, provider):
        provider.ls = AsyncMock(return_value=[])
        result = await action_registry.execute_action("documents.tree", {"path": "knowledge", "depth": 99}, {})
        assert result["success"] is True


class TestDocumentsHeadTail:
    @pytest.mark.asyncio
    async def test_head(self, provider):
        provider.cat = AsyncMock(return_value=VFSResource(
            path="knowledge/d/content.lines",
            lines=[f"L{i}: x" for i in range(1, 31)],
        ))
        result = await action_registry.execute_action("documents.head", {"path": "knowledge/d/content.lines", "lines": 5}, {})
        assert result["success"] is True
        assert len(result["head"]) == 5
        assert result["line_count"] == 30

    @pytest.mark.asyncio
    async def test_tail(self, provider):
        provider.cat = AsyncMock(return_value=VFSResource(
            path="knowledge/d/content.lines",
            lines=[f"L{i}: x" for i in range(1, 31)],
        ))
        result = await action_registry.execute_action("documents.tail", {"path": "knowledge/d/content.lines", "lines": 3}, {})
        assert result["success"] is True
        assert len(result["tail"]) == 3
        assert result["tail"][0] == "L28: x"

    @pytest.mark.asyncio
    async def test_head_no_provider(self):
        with patch("core.vfs_registry.resolve_provider", return_value=None):
            result = await action_registry.execute_action("documents.head", {"path": "knowledge/d"}, {})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_tail_no_provider(self):
        with patch("core.vfs_registry.resolve_provider", return_value=None):
            result = await action_registry.execute_action("documents.tail", {"path": "knowledge/d"}, {})
        assert result["success"] is False
        assert result["error"] == "no_provider"


# ============================================================================
# documents.scan / map / reduce
# ============================================================================

class TestDocumentsScan:
    @pytest.mark.asyncio
    async def test_scan_returns_files(self, provider):
        provider.scan = AsyncMock(return_value=[
            VFSNode(name="a.txt", type="file", path="knowledge/d/a.txt", size=10),
            VFSNode(name="b.txt", type="file", path="knowledge/d/b.txt", size=20),
        ])
        result = await action_registry.execute_action("documents.scan", {"path": "knowledge/d"}, {})
        assert result["success"] is True
        assert result["file_count"] == 2
        assert result["files"][0]["size"] == 10

    @pytest.mark.asyncio
    async def test_scan_no_provider(self):
        with patch("core.vfs_registry.resolve_provider", return_value=None):
            result = await action_registry.execute_action("documents.scan", {"path": "knowledge/d"}, {})
        assert result["success"] is False


class TestDocumentsMap:
    @pytest.mark.asyncio
    async def test_map_requires_paths_and_op(self, provider):
        result = await action_registry.execute_action("documents.map", {"paths": [], "op": "cat"}, {})
        assert result["success"] is False
        result = await action_registry.execute_action("documents.map", {"paths": ["a"], "op": "bogus"}, {})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_map_cat_and_head(self, provider):
        provider.cat = AsyncMock(return_value=VFSResource(
            path="knowledge/d/content.lines",
            lines=[f"L{i}: x" for i in range(1, 26)],
        ))
        result = await action_registry.execute_action(
            "documents.map",
            {"paths": ["knowledge/d/a", "knowledge/d/b"], "op": "head", "lines": 3},
            {},
        )
        assert result["success"] is True
        assert result["items_processed"] == 2
        assert len(result["results"][0]["lines"]) == 3

        result = await action_registry.execute_action("documents.map", {"paths": ["knowledge/d/a"], "op": "cat"}, {})
        assert result["results"][0]["line_count"] == 25

    @pytest.mark.asyncio
    async def test_map_grep(self, provider):
        provider.grep = AsyncMock(return_value=[
            VFSCitation(path="knowledge/d/a", line=1, snippet="L1: hit"),
        ])
        result = await action_registry.execute_action(
            "documents.map",
            {"paths": ["knowledge/d/a"], "op": "grep", "pattern": "hit"},
            {},
        )
        assert result["success"] is True
        assert result["results"][0]["matches"][0]["line"] == 1

    @pytest.mark.asyncio
    async def test_map_grep_missing_pattern(self, provider):
        result = await action_registry.execute_action(
            "documents.map",
            {"paths": ["knowledge/d/a"], "op": "grep"},
            {},
        )
        assert result["results"][0]["error"] == "pattern required for grep"

    @pytest.mark.asyncio
    async def test_map_no_provider_item(self):
        with patch("core.vfs_registry.resolve_provider", return_value=None):
            result = await action_registry.execute_action(
                "documents.map", {"paths": ["knowledge/d/a"], "op": "cat"}, {}
            )
        assert result["results"][0]["error"] == "no_provider"

    @pytest.mark.asyncio
    async def test_map_item_exception_tolerated(self, provider):
        provider.cat = AsyncMock(side_effect=RuntimeError("cat exploded"))
        result = await action_registry.execute_action(
            "documents.map", {"paths": ["knowledge/d/a"], "op": "cat"}, {}
        )
        assert result["results"][0]["error"] == "item_failed"

    @pytest.mark.asyncio
    async def test_map_fanout_capped(self, provider):
        provider.cat = AsyncMock(return_value=VFSResource(path="p", lines=["L1: x"]))
        paths = [f"knowledge/d/{i}" for i in range(60)]
        result = await action_registry.execute_action(
            "documents.map", {"paths": paths, "op": "cat", "max_items": 5}, {}
        )
        assert result["items_processed"] == 5


class TestDocumentsReduce:
    @pytest.mark.asyncio
    async def test_reduce_requires_items_and_mode(self):
        result = await action_registry.execute_action("documents.reduce", {"items": [], "mode": "count"}, {})
        assert result["success"] is False
        result = await action_registry.execute_action("documents.reduce", {"items": [{"path": "a"}], "mode": "bogus"}, {})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_reduce_count(self):
        result = await action_registry.execute_action("documents.reduce", {
            "items": [
                {"path": "a", "lines": ["L1: x", "L2: y"]},
                {"path": "b", "line_count": 7, "matches": [{"path": "b", "line": 1}]},
                {"path": "c"},
            ],
            "mode": "count",
        }, {})
        assert result["success"] is True
        assert result["total_lines"] == 9
        assert result["match_count"] == 1

    @pytest.mark.asyncio
    async def test_reduce_concat(self):
        result = await action_registry.execute_action("documents.reduce", {
            "items": [{"path": "a", "lines": ["L1: x"]}, {"path": "b"}],
            "mode": "concat",
        }, {})
        assert result["line_count"] == 1
        assert result["lines"] == ["L1: x"]

    @pytest.mark.asyncio
    async def test_reduce_unique(self):
        result = await action_registry.execute_action("documents.reduce", {
            "items": [
                {"path": "a", "matches": [{"path": "x", "line": 1}, {"path": "x", "line": 2}, {"path": "y", "line": 1}]},
            ],
            "mode": "unique",
        }, {})
        assert result["unique_count"] == 2
        assert result["paths"] == ["x", "y"]


class TestDocumentsAskImage:
    @pytest.mark.asyncio
    async def test_ask_image_requires_path_and_prompt(self, provider):
        result = await action_registry.execute_action("documents.ask_image", {"path": "img", "prompt": ""}, {})
        assert result["success"] is False
        result = await action_registry.execute_action("documents.ask_image", {}, {})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_ask_image_success(self, provider):
        provider.ask_image = AsyncMock(return_value={
            "success": True, "answer": "a chart with bars",
        })
        result = await action_registry.execute_action(
            "documents.ask_image", {"path": "knowledge/img.png", "prompt": "describe"}, {}
        )
        assert result["success"] is True
        assert result["answer"] == "a chart with bars"
        assert result["path"] == "knowledge/img.png"

    @pytest.mark.asyncio
    async def test_ask_image_no_provider(self):
        with patch("core.vfs_registry.resolve_provider", return_value=None):
            result = await action_registry.execute_action(
                "documents.ask_image", {"path": "knowledge/img.png", "prompt": "q"}, {}
            )
        assert result["success"] is False
        assert result["error"] == "no_provider"


# ============================================================================
# Legacy search path (flag-off) + context helpers + lazy wrappers
# ============================================================================

class TestLegacyAndWrappers:
    @pytest.mark.asyncio
    async def test_legacy_search_knowledge_branch(self):
        ingested_doc = MagicMock(id="i1", file_name="f.txt", content_preview="hello world")
        knowledge_doc = MagicMock(id="k1", title="kb", content="deep knowledge")

        ingested_q = MagicMock()
        ingested_q.all.return_value = [ingested_doc]
        ingested_q.limit.return_value = ingested_q
        knowledge_q = MagicMock()
        knowledge_q.all.return_value = [knowledge_doc]
        knowledge_q.limit.return_value = knowledge_q

        db = MagicMock()
        db.query.side_effect = [
            MagicMock(filter=MagicMock(return_value=ingested_q)),
            MagicMock(filter=MagicMock(return_value=knowledge_q)),
        ]
        ctx_manager = MagicMock()
        ctx_manager.return_value.__enter__.return_value = db
        ctx_manager.return_value.__exit__.return_value = False

        with patch("core.database.get_db_session", ctx_manager), patch(
            "core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=False
        ):
            result = await action_registry.execute_action("documents.search", {"query": "world", "limit": 10}, {})
        assert result["success"] is True
        assert [r["source"] for r in result["results"]] == ["ingested", "knowledge"]

    def test_vfs_context_extracts_workspace_and_user(self):
        from types import SimpleNamespace

        from core.action_registry import _vfs_context

        user = SimpleNamespace(workspace_id="ws-1")
        ctx = _vfs_context({"user": user, "user_id": "u-1"})
        assert ctx == {"workspace_id": "ws-1", "user_id": "u-1"}

    @pytest.mark.asyncio
    async def test_mini_app_db_query_wrapper(self):
        with patch("tools.mini_app_tool.mini_app_db_query", new=AsyncMock(return_value={"success": True})) as m:
            result = await action_registry.execute_action("mini_app_db_query", {"canvas_id": "c"}, {})
        assert result["success"] is True
        m.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_mini_app_db_write_wrapper(self):
        with patch("tools.mini_app_tool.mini_app_db_write", new=AsyncMock(return_value={"success": True})) as m:
            result = await action_registry.execute_action("mini_app_db_write", {"canvas_id": "c", "op": "append"}, {})
        assert result["success"] is True
        m.assert_awaited_once()

    def test_documents_search_action_registered(self):
        from core.action_registry import action_registry as reg

        assert "documents.search" in reg.list_actions()
        for name in ("ls", "cat", "grep", "tree", "head", "tail", "scan", "map", "reduce", "ask_image"):
            assert f"documents.{name}" in reg.list_actions()


class TestDisabledBranches:
    """Every VFS action degrades to vfs_disabled when the flag is off."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("name,args", [
        ("documents.cat", {"path": "knowledge/d"}),
        ("documents.grep", {"pattern": "x", "path_prefix": "knowledge"}),
        ("documents.tree", {"path": "knowledge"}),
        ("documents.head", {"path": "knowledge/d"}),
        ("documents.tail", {"path": "knowledge/d"}),
        ("documents.scan", {"path": "knowledge/d"}),
        ("documents.map", {"paths": ["a"], "op": "cat"}),
        ("documents.reduce", {"items": [{"path": "a"}], "mode": "count"}),
        ("documents.ask_image", {"path": "knowledge/i.png", "prompt": "q"}),
    ])
    async def test_vfs_action_disabled(self, name, args):
        with patch("core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=False):
            result = await action_registry.execute_action(name, args, {})
        assert result["success"] is False
        assert result["error"] == "vfs_disabled"


class TestLegacyErrorPaths:
    @pytest.mark.asyncio
    async def test_legacy_search_empty_query(self):
        with patch("core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=False):
            result = await action_registry.execute_action("documents.search", {"query": "  "}, {})
        assert result["success"] is False
        assert "query" in result["error"]

    @pytest.mark.asyncio
    async def test_legacy_search_exception_generic(self):
        ctx_manager = MagicMock()
        ctx_manager.return_value.__enter__.side_effect = RuntimeError("db down")
        ctx_manager.return_value.__exit__.return_value = False
        with patch("core.database.get_db_session", ctx_manager), patch(
            "core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=False
        ):
            result = await action_registry.execute_action("documents.search", {"query": "x"}, {})
        assert result["success"] is False
        assert result["error"] == "Document search failed"


class TestEnsureVfsRegistered:
    @pytest.mark.asyncio
    async def test_provider_registration_failure_tolerated(self):
        """_ensure_vfs_registered swallows provider-construction failures."""
        from core import action_registry as ar

        real_import = __import__

        def selective_import(name, *a, **kw):
            if name == "integrations.vfs.knowledge_vfs":
                raise ImportError("knowledge_vfs provider unavailable")
            return real_import(name, *a, **kw)

        with patch("core.vfs_registry.get_provider", return_value=None), patch(
            "core.vfs_registry.register_provider"
        ), patch(
            "core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True
        ), patch(
            "core.vfs_registry.resolve_provider", return_value=None
        ), patch(
            "builtins.__import__", side_effect=selective_import
        ):
            result = await action_registry.execute_action("documents.ls", {"path": "knowledge"}, {})
        assert result["success"] is False
        assert result["error"] == "no_provider"

    @pytest.mark.asyncio
    async def test_tree_nested_ls_failure_skipped(self, provider):
        provider.ls = AsyncMock(side_effect=[
            [VFSNode(name="d1", type="dir", path="knowledge/d1")],
            RuntimeError("boom"),
        ])
        result = await action_registry.execute_action("documents.tree", {"path": "knowledge"}, {})
        assert result["success"] is True
        assert any("d1" in line for line in result["tree"])
