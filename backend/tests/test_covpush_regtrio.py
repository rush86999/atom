"""Coverage push for core/action_registry.py and core/generic_agent.py."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from pydantic import BaseModel

from core.action_registry import (
    ActionDefinition,
    ActionRegistry,
    action_registry,
    register_action,
)
from core.generic_agent import GenericAgent
from core.models import AgentRegistry
from core.react_models import ReActStep, ToolCall


class TestRegistryMechanicsExtra:
    def test_action_definition_description_fallback_from_docstring(self):
        async def handler(args, context):
            """Handler docstring."""

            return {}

        action = ActionDefinition("a.b", handler)
        assert action.description == "Handler docstring."

    def test_action_definition_description_unnamed_fallback(self):
        async def handler(args, context):
            return {}

        handler.__doc__ = None
        action = ActionDefinition("a.b", handler)
        assert action.description == "Action a.b"

    def test_action_definition_default_schema(self):
        async def handler(args, context):
            return {}

        action = ActionDefinition("a.b", handler, description="d")
        assert action.parameters_schema == {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def test_register_overwrites_and_returns_definition(self):
        reg = ActionRegistry()

        async def h1(args, context):
            return 1

        async def h2(args, context):
            return 2

        first = reg.register("x", h1, description="one")
        assert first.name == "x"
        second = reg.register("x", h2, description="two")
        assert second.description == "two"
        assert reg.get_action("x") is second
        assert len(reg.get_all_definitions()) == 1

    def test_list_action_names_alias(self):
        reg = ActionRegistry()

        async def h(args, context):
            return {}

        reg.register("z", h)
        reg.register("a", h)
        assert reg.list_action_names() == ["a", "z"]
        assert reg.list_action_names() == reg.list_actions()

    def test_get_all_definitions_is_a_copy(self):
        reg = ActionRegistry()

        async def h(args, context):
            return {}

        reg.register("g", h)
        definitions = reg.get_all_definitions()
        definitions.clear()
        assert len(reg.get_all_definitions()) == 1

    @pytest.mark.asyncio
    async def test_execute_action_passes_context_through(self):
        reg = ActionRegistry()

        async def h(args, context):
            return context

        reg.register("ctx", h)
        result = await reg.execute_action("ctx", {}, {"k": "v"})
        assert result == {"k": "v"}

    @pytest.mark.asyncio
    async def test_execute_action_unknown_is_lookup_error(self):
        reg = ActionRegistry()
        with pytest.raises(LookupError):
            await reg.execute_action("missing", {}, {})

    def test_register_action_decorator_with_schema(self):
        @register_action("test.covpush.schema.action")
        async def _h(args, context):
            return {}

        action = action_registry.get_action("test.covpush.schema.action")
        assert action is not None
        assert isinstance(action.parameters_schema["properties"], dict)


class TestContextUserId:
    def test_empty_context_returns_none(self):
        from core.action_registry import _context_user_id

        assert _context_user_id({}) is None
        assert _context_user_id(None) is None

    def test_user_id_keys_extracted(self):
        from core.action_registry import _context_user_id

        assert _context_user_id({"user_id": "u1"}) == "u1"
        assert _context_user_id({"userId": "u2"}) == "u2"
        assert _context_user_id({"actor_id": "u3"}) == "u3"
        assert _context_user_id({"user_id": None, "userId": "u4"}) == "u4"

    def test_user_object_extracted(self):
        from core.action_registry import _context_user_id

        user = SimpleNamespace(id="uid-42")
        assert _context_user_id({"user": user}) == "uid-42"

    def test_user_object_without_id_returns_none(self):
        from core.action_registry import _context_user_id

        assert _context_user_id({"user": object()}) is None


class TestVfsHelpers:
    def test_vfs_disabled_envelope(self):
        from core.action_registry import _vfs_disabled

        out = _vfs_disabled()
        assert out["success"] is False
        assert out["error"] == "vfs_disabled"

    def test_vfs_context_from_user_dict(self):
        from core.action_registry import _vfs_context

        class _User:
            def __init__(self):
                self.workspace_id = "ws-1"

        ctx = _vfs_context({"user": _User(), "user_id": "u1"})
        assert ctx == {"workspace_id": "ws-1", "user_id": "u1"}

    def test_vfs_context_fallback(self):
        from core.action_registry import _vfs_context

        ctx = _vfs_context({"workspace_id": "ws-2", "user_id": "u2"})
        assert ctx == {"workspace_id": "ws-2", "user_id": "u2"}

    def test_ensure_vfs_registered_already_present(self):
        from core.action_registry import _ensure_vfs_registered

        with patch("core.vfs_registry.get_provider", return_value="existing"):
            _ensure_vfs_registered()

    def test_ensure_vfs_registered_registration_failure_swallowed(self):
        from core.action_registry import _ensure_vfs_registered

        with patch("core.vfs_registry.get_provider", return_value=None), patch(
            "integrations.vfs.knowledge_vfs.KnowledgeVFSProvider",
            side_effect=RuntimeError("boom"),
        ):
            _ensure_vfs_registered()

    def test_ensure_vfs_registered_registers_provider(self):
        from core.action_registry import _ensure_vfs_registered

        with patch(
            "core.vfs_registry.get_provider", return_value=None
        ), patch(
            "integrations.vfs.knowledge_vfs.KnowledgeVFSProvider", return_value="prov"
        ) as cls, patch("core.vfs_registry.register_provider") as register:
            _ensure_vfs_registered()
            register.assert_called_once_with("prov")
            cls.assert_called_once_with()


class _FakeVFSProvider:
    def __init__(self):
        self.ls = AsyncMock(return_value=[])
        self.cat = AsyncMock()
        self.grep = AsyncMock(return_value=[])
        self.scan = AsyncMock(return_value=[])
        self.ask_image = AsyncMock(return_value={"success": True, "answer": "yes"})


def _vfs_node(name, type_, path):
    return SimpleNamespace(name=name, type=type_, path=path)


class TestDocumentsSearchAction:
    @pytest.mark.asyncio
    async def test_empty_query_returns_error(self):
        out = await action_registry.execute_action("documents.search", {"query": "  "}, {})
        assert out["success"] is False
        assert "query is required" in out["error"]

    @pytest.mark.asyncio
    async def test_hybrid_path_success(self):
        svc = MagicMock()
        svc.search = AsyncMock(
            return_value={
                "success": True,
                "query": "q",
                "results": [{"id": "1"}],
                "hybrid": True,
            }
        )
        with patch(
            "core.hybrid_search.documents_hybrid.DocumentsHybridSearch", return_value=svc
        ):
            out = await action_registry.execute_action(
                "documents.search",
                {
                    "query": "hello",
                    "limit": 5,
                    "since": "2026-01-01",
                    "source": "ingested",
                    "author": "me",
                },
                {},
            )
        assert out["success"] is True
        svc.search.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_hybrid_path_exception(self):
        with patch(
            "core.hybrid_search.documents_hybrid.DocumentsHybridSearch",
            side_effect=RuntimeError("boom"),
        ):
            out = await action_registry.execute_action("documents.search", {"query": "q"}, {})
        assert out["success"] is False
        assert out["error"] == "Document search failed"

    @pytest.mark.asyncio
    async def test_legacy_path_when_vfs_disabled(self):
        from core.models import IngestedDocument, KnowledgeDocument

        session = MagicMock()

        def _query(model):
            if model is IngestedDocument:
                q = MagicMock()
                q.filter.return_value.limit.return_value.all.return_value = [
                    SimpleNamespace(id="i1", file_name="alpha.pdf", content_preview="preview a"),
                    SimpleNamespace(id="i2", file_name="beta.pdf", content_preview="preview b"),
                ]
                return q
            q = MagicMock()
            q.filter.return_value.limit.return_value.all.return_value = [
                SimpleNamespace(id="k1", title="gamma", content="content c"),
            ]
            return q

        session.query.side_effect = _query
        cm = MagicMock()
        cm.__enter__.return_value = session
        with patch(
            "core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=False
        ), patch("core.database.get_db_session", return_value=cm):
            out = await action_registry.execute_action(
                "documents.search", {"query": "alpha", "limit": 10}, {}
            )
        assert out["success"] is True
        assert len(out["results"]) == 3
        assert out["results"][0]["source"] == "ingested"
        assert out["results"][2]["source"] == "knowledge"

    @pytest.mark.asyncio
    async def test_legacy_path_exception(self):
        with patch(
            "core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=False
        ), patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            out = await action_registry.execute_action("documents.search", {"query": "alpha"}, {})
        assert out["success"] is False
        assert out["error"] == "Document search failed"

    @pytest.mark.asyncio
    async def test_malformed_limit_raises_uncaught(self):
        with pytest.raises(ValueError):
            await action_registry.execute_action(
                "documents.search", {"query": "alpha", "limit": "abc"}, {}
            )


class TestCanvasActions:
    @pytest.mark.asyncio
    async def test_canvas_read_missing_id(self):
        out = await action_registry.execute_action("canvas.read", {}, {})
        assert out["success"] is False
        assert "canvas_id" in out["error"]

    @pytest.mark.asyncio
    async def test_canvas_read_missing_user(self):
        out = await action_registry.execute_action("canvas.read", {"canvas_id": "c1"}, {})
        assert out["success"] is False
        assert "Authenticated user" in out["error"]

    @pytest.mark.asyncio
    async def test_canvas_read_success(self):
        with patch(
            "tools.canvas_crud_tool.read_canvas",
            new=AsyncMock(return_value={"success": True, "canvas": {"id": "c1"}}),
        ) as read_canvas:
            out = await action_registry.execute_action(
                "canvas.read", {"canvas_id": "c1"}, {"user_id": "u1"}
            )
        assert out == {"success": True, "canvas": {"id": "c1"}}
        read_canvas.assert_awaited_once_with("u1", "c1")

    @pytest.mark.asyncio
    async def test_canvas_update_missing_args(self):
        out = await action_registry.execute_action("canvas.update", {"canvas_id": "c1"}, {})
        assert out["success"] is False
        out = await action_registry.execute_action("canvas.update", {"content": {}}, {})
        assert out["success"] is False

    @pytest.mark.asyncio
    async def test_canvas_update_missing_user(self):
        out = await action_registry.execute_action(
            "canvas.update", {"canvas_id": "c1", "content": {}}, {}
        )
        assert out["success"] is False
        assert "Authenticated user" in out["error"]

    @pytest.mark.asyncio
    async def test_canvas_update_success(self):
        with patch(
            "tools.canvas_crud_tool.update_canvas_content",
            new=AsyncMock(return_value={"success": True}),
        ) as update_canvas_content:
            out = await action_registry.execute_action(
                "canvas.update",
                {
                    "canvas_id": "c1",
                    "content": {"blocks": []},
                    "canvas_type": "board",
                    "title": "T",
                },
                {"user_id": "u1"},
            )
        assert out["success"] is True
        update_canvas_content.assert_awaited_once()
        assert update_canvas_content.await_args.kwargs["content"] == {"blocks": []}
        assert update_canvas_content.await_args.kwargs["canvas_type"] == "board"


class TestTasksCreateAction:
    @pytest.mark.asyncio
    async def test_missing_title_or_board(self):
        out = await action_registry.execute_action("tasks.create", {"title": "t"}, {})
        assert out["success"] is False
        out = await action_registry.execute_action("tasks.create", {"board_id": "b"}, {})
        assert out["success"] is False

    @pytest.mark.asyncio
    async def test_success(self):
        svc = MagicMock()
        svc.create_task.return_value = SimpleNamespace(
            id="task-1", board_id="b1", column_id="c1", title="T",
            description="D", status="backlog",
        )
        session = MagicMock()
        cm = MagicMock()
        cm.__enter__.return_value = session
        with patch("core.board_service.BoardService", return_value=svc), patch(
            "core.database.get_db_session", return_value=cm
        ):
            out = await action_registry.execute_action(
                "tasks.create",
                {"title": "T", "board_id": "b1", "description": "D", "priority": "high"},
                {"user_id": "u1"},
            )
        assert out["success"] is True
        assert out["task"]["id"] == "task-1"
        svc.create_task.assert_called_once()
        assert svc.create_task.call_args.kwargs["board_id"] == "b1"
        assert svc.create_task.call_args.kwargs["created_by_user_id"] == "u1"
        assert svc.create_task.call_args.kwargs["payload"].priority == "high"

    @pytest.mark.asyncio
    async def test_exception(self):
        with patch(
            "core.board_service.BoardService", side_effect=RuntimeError("boom")
        ), patch("core.database.get_db_session", return_value=MagicMock()):
            out = await action_registry.execute_action(
                "tasks.create", {"title": "T", "board_id": "b1"}, {}
            )
        assert out["success"] is False
        assert out["error"] == "Task creation failed"


class TestAgentsListAction:
    @pytest.mark.asyncio
    async def test_success_with_category(self):
        session = MagicMock()
        agent = SimpleNamespace(
            id="a1", name="A", description="d", status="active",
            category="general", capabilities=["web"],
        )
        q = MagicMock()
        q.filter.return_value.all.return_value = [agent]
        session.query.return_value = q
        cm = MagicMock()
        cm.__enter__.return_value = session
        with patch("core.database.get_db_session", return_value=cm):
            out = await action_registry.execute_action(
                "agents.list", {"category": "general"}, {}
            )
        assert out["success"] is True
        assert out["agents"][0]["id"] == "a1"
        q.filter.assert_called_once()

    @pytest.mark.asyncio
    async def test_success_without_category(self):
        session = MagicMock()
        q = MagicMock()
        q.all.return_value = []
        session.query.return_value = q
        cm = MagicMock()
        cm.__enter__.return_value = session
        with patch("core.database.get_db_session", return_value=cm):
            out = await action_registry.execute_action("agents.list", {}, {})
        assert out["success"] is True
        assert out["agents"] == []

    @pytest.mark.asyncio
    async def test_exception(self):
        with patch("core.database.get_db_session", side_effect=RuntimeError("boom")):
            out = await action_registry.execute_action("agents.list", {}, {})
        assert out["success"] is False
        assert out["agents"] == []


class TestVfsActions:
    def _ctx(self):
        return {"workspace_id": "ws-1", "user_id": "u1"}

    @pytest.mark.asyncio
    async def test_vfs_actions_disabled(self):
        with patch("core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=False):
            for name in (
                "documents.ls", "documents.cat", "documents.grep", "documents.tree",
                "documents.head", "documents.tail", "documents.scan", "documents.map",
                "documents.reduce", "documents.ask_image",
            ):
                out = await action_registry.execute_action(name, {"path": "x"}, {})
                assert out["success"] is False
                assert out["error"] == "vfs_disabled"

    @pytest.mark.asyncio
    async def test_ls_success_and_no_provider(self):
        provider = _FakeVFSProvider()
        provider.ls.return_value = [_vfs_node("a.txt", "file", "knowledge/a.txt")]
        with patch(
            "core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True
        ), patch("core.vfs_registry.resolve_provider", return_value=provider):
            out = await action_registry.execute_action(
                "documents.ls", {"path": "knowledge"}, self._ctx()
            )
        assert out["success"] is True
        assert out["entries"][0]["name"] == "a.txt"
        provider.ls.assert_awaited_once()

        with patch(
            "core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True
        ), patch("core.vfs_registry.resolve_provider", return_value=None):
            out = await action_registry.execute_action("documents.ls", {"path": "unknown"}, {})
        assert out["success"] is False
        assert out["error"] == "no_provider"

    @pytest.mark.asyncio
    async def test_cat_success(self):
        provider = _FakeVFSProvider()
        provider.cat.return_value = SimpleNamespace(
            to_dict=lambda: {"path": "p", "lines": ["L1: x"]}
        )
        with patch(
            "core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True
        ), patch("core.vfs_registry.resolve_provider", return_value=provider):
            out = await action_registry.execute_action(
                "documents.cat", {"path": "knowledge/p"}, self._ctx()
            )
        assert out["success"] is True
        assert out["path"] == "p"

    @pytest.mark.asyncio
    async def test_grep_success(self):
        provider = _FakeVFSProvider()
        provider.grep.return_value = [
            SimpleNamespace(to_dict=lambda: {"path": "p", "line": 1})
        ]
        with patch(
            "core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True
        ), patch("core.vfs_registry.resolve_provider", return_value=provider):
            out = await action_registry.execute_action(
                "documents.grep", {"pattern": "foo", "path_prefix": "knowledge"}, self._ctx()
            )
        assert out["success"] is True
        assert out["matches"][0]["path"] == "p"
        provider.grep.assert_awaited_once_with("foo", "knowledge", self._ctx())

    @pytest.mark.asyncio
    async def test_tree_success_with_dirs(self):
        provider = _FakeVFSProvider()
        provider.ls.side_effect = [
            [
                _vfs_node("sub", "dir", "knowledge/sub"),
                _vfs_node("a.txt", "file", "knowledge/a.txt"),
            ],
            [_vfs_node("b.txt", "file", "knowledge/sub/b.txt")],
        ]
        with patch(
            "core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True
        ), patch("core.vfs_registry.resolve_provider", return_value=provider):
            out = await action_registry.execute_action(
                "documents.tree", {"path": "knowledge", "depth": 3}, self._ctx()
            )
        assert out["success"] is True
        assert any("└─sub/" in line for line in out["tree"])
        assert any("a.txt" in line for line in out["tree"])

    @pytest.mark.asyncio
    async def test_tree_ls_failure_degrades(self):
        provider = _FakeVFSProvider()
        provider.ls.side_effect = RuntimeError("ls boom")
        with patch(
            "core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True
        ), patch("core.vfs_registry.resolve_provider", return_value=provider):
            out = await action_registry.execute_action(
                "documents.tree", {"path": "knowledge"}, {}
            )
        assert out["success"] is True
        assert out["tree"] == ["knowledge"]

    @pytest.mark.asyncio
    async def test_head_and_tail(self):
        provider = _FakeVFSProvider()
        provider.cat.return_value = SimpleNamespace(
            path="p", lines=[f"L{i}: line" for i in range(5)]
        )
        with patch(
            "core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True
        ), patch("core.vfs_registry.resolve_provider", return_value=provider):
            out = await action_registry.execute_action(
                "documents.head", {"path": "p", "lines": 2}, {}
            )
            assert out["head"] == ["L0: line", "L1: line"]
            out = await action_registry.execute_action(
                "documents.tail", {"path": "p", "lines": 2}, {}
            )
            assert out["tail"] == ["L3: line", "L4: line"]
            out = await action_registry.execute_action(
                "documents.head", {"path": "p", "lines": 0}, {}
            )
            assert len(out["head"]) == 1

    @pytest.mark.asyncio
    async def test_scan_success(self):
        provider = _FakeVFSProvider()
        provider.scan.return_value = [
            SimpleNamespace(path="knowledge/a.txt", size=10),
            SimpleNamespace(path="knowledge/b.txt", size=20),
        ]
        with patch(
            "core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True
        ), patch("core.vfs_registry.resolve_provider", return_value=provider):
            out = await action_registry.execute_action(
                "documents.scan", {"path": "knowledge", "max_depth": 2}, {}
            )
        assert out["success"] is True
        assert out["file_count"] == 2
        provider.scan.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_map_ops(self):
        provider = _FakeVFSProvider()
        provider.cat.return_value = SimpleNamespace(path="p", lines=["L1: x", "L2: y"])
        provider.grep.return_value = [
            SimpleNamespace(to_dict=lambda: {"path": "p", "line": 1})
        ]
        with patch(
            "core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True
        ), patch("core.vfs_registry.resolve_provider", return_value=provider):
            out = await action_registry.execute_action(
                "documents.map", {"paths": ["knowledge/p"], "op": "cat"}, {}
            )
            assert out["results"][0]["line_count"] == 2
            out = await action_registry.execute_action(
                "documents.map", {"paths": ["knowledge/p"], "op": "head", "lines": 1}, {}
            )
            assert out["results"][0]["lines"] == ["L1: x"]
            out = await action_registry.execute_action(
                "documents.map", {"paths": ["knowledge/p"], "op": "grep", "pattern": "x"}, {}
            )
            assert out["results"][0]["matches"][0]["path"] == "p"

    @pytest.mark.asyncio
    async def test_map_validation_and_errors(self):
        with patch("core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True):
            out = await action_registry.execute_action(
                "documents.map", {"paths": [], "op": "cat"}, {}
            )
            assert out["success"] is False
            out = await action_registry.execute_action(
                "documents.map", {"paths": ["p"], "op": "bogus"}, {}
            )
            assert out["success"] is False

        provider = _FakeVFSProvider()
        provider.cat.side_effect = RuntimeError("cat boom")
        with patch(
            "core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True
        ), patch("core.vfs_registry.resolve_provider", return_value=provider):
            out = await action_registry.execute_action(
                "documents.map", {"paths": ["knowledge/p"], "op": "cat"}, {}
            )
            assert out["results"][0]["error"] == "item_failed"

        with patch(
            "core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True
        ), patch("core.vfs_registry.resolve_provider", return_value=None):
            out = await action_registry.execute_action(
                "documents.map", {"paths": ["nope/p"], "op": "cat"}, {}
            )
            assert out["results"][0]["error"] == "no_provider"

    @pytest.mark.asyncio
    async def test_map_grep_missing_pattern(self):
        provider = _FakeVFSProvider()
        with patch(
            "core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True
        ), patch("core.vfs_registry.resolve_provider", return_value=provider):
            out = await action_registry.execute_action(
                "documents.map", {"paths": ["knowledge/p"], "op": "grep"}, {}
            )
        assert out["results"][0]["error"] == "pattern required for grep"

    @pytest.mark.asyncio
    async def test_reduce_modes(self):
        with patch("core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True):
            out = await action_registry.execute_action(
                "documents.reduce",
                {
                    "items": [{"lines": ["a", "b"]}, {"line_count": 3}, {"matches": [1, 2]}],
                    "mode": "count",
                },
                {},
            )
            assert out["total_lines"] == 5
            assert out["match_count"] == 2
            out = await action_registry.execute_action(
                "documents.reduce",
                {"items": [{"lines": ["a"]}, {"lines": ["b"]}], "mode": "concat"},
                {},
            )
            assert out["lines"] == ["a", "b"]
            out = await action_registry.execute_action(
                "documents.reduce",
                {"items": [{"matches": [{"path": "p1"}, {"path": "p1"}, {"path": ""}]}], "mode": "unique"},
                {},
            )
            assert out["paths"] == ["p1"]
            assert out["unique_count"] == 1

    @pytest.mark.asyncio
    async def test_reduce_validation(self):
        with patch("core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True):
            out = await action_registry.execute_action(
                "documents.reduce", {"items": [], "mode": "count"}, {}
            )
            assert out["success"] is False
            out = await action_registry.execute_action(
                "documents.reduce", {"items": [{}], "mode": "sum"}, {}
            )
            assert out["success"] is False

    @pytest.mark.asyncio
    async def test_ask_image_paths(self):
        with patch(
            "core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True
        ), patch("core.vfs_registry.resolve_provider", return_value=None):
            out = await action_registry.execute_action(
                "documents.ask_image", {"path": "p", "prompt": "what?"}, {}
            )
            assert out["success"] is False
            assert out["error"] == "no_provider"

        provider = _FakeVFSProvider()
        provider.ask_image.return_value = {"success": True, "answer": "a cat"}
        with patch(
            "core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True
        ), patch("core.vfs_registry.resolve_provider", return_value=provider):
            out = await action_registry.execute_action(
                "documents.ask_image", {"path": "knowledge/img.png", "prompt": "what?"}, {}
            )
            assert out["success"] is True
            assert out["answer"] == "a cat"

    @pytest.mark.asyncio
    async def test_ask_image_missing_args(self):
        with patch("core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True):
            out = await action_registry.execute_action("documents.ask_image", {"path": ""}, {})
            assert out["success"] is False
            assert "path and prompt" in out["error"]


class TestMiniAppPassthroughs:
    @pytest.mark.parametrize(
        "name",
        [
            "mini_app_scaffold",
            "mini_app_write_logic",
            "mini_app_dev_run",
            "mini_app_publish",
            "mini_app_install",
            "mini_app_run",
            "mini_app_list",
            "mini_app_get_state",
            "mini_app_db_query",
            "mini_app_db_write",
            "mini_app_set_tests",
            "mini_app_run_tests",
            "mini_app_logic_history",
            "mini_app_revert_logic",
            "mini_app_status",
        ],
    )
    @pytest.mark.asyncio
    async def test_mini_app_handlers_delegate(self, name):
        with patch(
            f"tools.mini_app_tool.{name}", new=AsyncMock(return_value={"ok": name})
        ) as m:
            out = await action_registry.execute_action(name, {"app_id": "a1"}, {"user_id": "u1"})
        assert out == {"ok": name}
        m.assert_awaited_once_with({"app_id": "a1"}, {"user_id": "u1"})

    def test_mini_app_actions_single_registration(self):
        assert action_registry.list_actions().count("mini_app_db_query") == 1
        assert action_registry.list_actions().count("mini_app_db_write") == 1


def _agent_model(**cfg_overrides):
    config = {
        "system_prompt": "You are Test Agent.",
        "tools": "*",
        "max_steps": 3,
        **cfg_overrides,
    }
    return AgentRegistry(
        id="agent-123",
        name="Test Agent",
        type="assistant",
        module_path="agents.assistant",
        class_name="AssistantAgent",
        category="general",
        configuration=config,
    )


def _build_agent(model, **patches):
    with patch("core.generic_agent.WorldModelService"), patch(
        "core.generic_agent.ReflectionService"
    ), patch("core.generic_agent.CanvasSummaryService"), patch(
        "core.generic_agent.mcp_service"
    ), patch("core.generic_agent.LLMService"):
        agent = GenericAgent(model)
    for k, v in patches.items():
        setattr(agent, k, v)
    return agent


def _exec_ready(agent):
    agent.world_model.recall_experiences = AsyncMock(return_value={})
    agent.mcp.get_all_tools = AsyncMock(return_value=[])
    agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
    agent.reflection_service.generate_critique = AsyncMock()
    agent._record_execution = AsyncMock()
    agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})


class TestGenericAgentRadioAndMaturity:
    @pytest.mark.asyncio
    async def test_radio_drain_and_maturity_fallback(self):
        agent = _build_agent(_agent_model())
        _exec_ready(agent)
        agent._react_step = AsyncMock(return_value=ReActStep(thought="done", final_answer="fin"))
        with patch(
            "core.database.get_db_session", side_effect=RuntimeError("db down")
        ), patch(
            "core.agent_radio.radio_service.inbox_drain_text", return_value="RADIO: hello"
        ):
            result = await agent.execute("do it", {"radio_thread_id": "rt-1"})
        assert result["status"] == "success"
        assert result["output"] == "fin"
        assert agent._react_step.await_args.args[2] == "RADIO: hello"

    @pytest.mark.asyncio
    async def test_radio_drain_failure_is_swallowed(self):
        agent = _build_agent(_agent_model())
        _exec_ready(agent)
        agent._react_step = AsyncMock(return_value=ReActStep(thought="done", final_answer="fin"))
        with patch(
            "core.agent_radio.radio_service.inbox_drain_text",
            side_effect=RuntimeError("radio boom"),
        ):
            result = await agent.execute("do it", {"radio_thread_id": "rt-1"})
        assert result["status"] == "success"
        assert agent._react_step.await_args.args[2] == ""

    @pytest.mark.asyncio
    async def test_measure_success_rate_exception_returns_none(self):
        agent = _build_agent(_agent_model())
        with patch(
            "core.agent_graduation_service.AgentGraduationService",
            side_effect=RuntimeError("grad boom"),
        ):
            assert await agent._measure_success_rate() is None


class TestGenericAgentParallelPaths:
    @pytest.mark.asyncio
    async def test_parallel_params_model_dump(self):
        class _Params(BaseModel):
            q: str = "x"

        agent = _build_agent(_agent_model())
        _exec_ready(agent)
        tc = ToolCall(tool="t1")
        tc.params = _Params()
        agent._react_step = AsyncMock(
            side_effect=[
                ReActStep(thought="parallel", actions=[tc], final_answer=None),
                ReActStep(thought="done", final_answer="finished"),
            ]
        )
        agent._execute_parallel_tools = AsyncMock(
            return_value=[
                {
                    "tool_name": "t1", "params": {}, "output": "ok",
                    "verified_kind": "unverified", "verified_evidence": None,
                }
            ]
        )
        with patch("core.hallucination_config.is_parallel_tools_enabled", return_value=True):
            result = await agent.execute("do it")
        assert result["status"] == "success"
        agent._execute_parallel_tools.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_parallel_stuck_halt(self):
        agent = _build_agent(_agent_model())
        _exec_ready(agent)
        tc = ToolCall(tool="t1", params={})
        step = ReActStep(thought="repeat", actions=[tc], final_answer=None)
        agent._react_step = AsyncMock(return_value=step)
        agent._execute_parallel_tools = AsyncMock(
            return_value=[
                {
                    "tool_name": "t1", "params": {}, "output": "ok",
                    "verified_kind": "unverified", "verified_evidence": None,
                }
            ]
        )
        with patch("core.hallucination_config.is_parallel_tools_enabled", return_value=True):
            result = await agent.execute(
                "do it",
                {"objective_goal": "g", "objective_done": lambda state: False},
            )
        assert result["status"] == "stuck"
        assert "repeated 3+ times" in result["output"]
        assert agent._execute_parallel_tools.await_count == 2

    @pytest.mark.asyncio
    async def test_single_action_stuck_halt(self):
        agent = _build_agent(_agent_model())
        _exec_ready(agent)
        agent._react_step = AsyncMock(
            return_value=ReActStep(thought="repeat", action=ToolCall(tool="same", params={}))
        )
        agent._step_act = AsyncMock(return_value="ok")
        with patch("core.hallucination_config.is_parallel_tools_enabled", return_value=False):
            result = await agent.execute(
                "do it",
                {"objective_goal": "g", "objective_done": lambda state: False},
            )
        assert result["status"] == "stuck"
        assert "identical arguments 3+ times" in result["output"]

    @pytest.mark.asyncio
    async def test_objective_satisfied_early_exit(self):
        agent = _build_agent(_agent_model())
        _exec_ready(agent)
        agent._react_step = AsyncMock(return_value=ReActStep(thought="planning"))
        with patch("core.hallucination_config.is_parallel_tools_enabled", return_value=False):
            result = await agent.execute(
                "do it",
                {"objective_goal": "g", "objective_done": lambda state: True},
            )
        assert result["status"] == "objective_satisfied"
        assert result["output"] == "planning"


class TestGenericAgentCustomActions:
    @pytest.mark.asyncio
    async def test_register_action_populates_specs(self):
        agent = _build_agent(_agent_model())

        async def handler(args, context):
            return {"ok": True}

        await agent.register_action("custom.echo", handler, description="desc", min_maturity="INTERN")
        assert "custom.echo" in agent._custom_actions
        assert agent._custom_action_specs["custom.echo"] == {
            "description": "desc",
            "min_maturity": "INTERN",
        }

    def test_custom_action_visibility_branches(self):
        agent = _build_agent(_agent_model())
        assert agent._custom_action_visible("unknown") is False
        agent._custom_action_specs["no_floor"] = {"description": "d", "min_maturity": None}
        assert agent._custom_action_visible("no_floor") is True
        agent._custom_action_specs["floored"] = {"description": "d", "min_maturity": "SUPERVISED"}
        assert agent._custom_action_visible("floored") is False
        agent._run_maturity = "STUDENT"
        assert agent._custom_action_visible("floored") is False
        agent._run_maturity = "SUPERVISED"
        assert agent._custom_action_visible("floored") is True
        agent._run_maturity = "AUTONOMOUS"
        assert agent._custom_action_visible("floored") is True
        agent._custom_action_specs["weird_floor"] = {
            "description": "d", "min_maturity": "NOT_A_TIER",
        }
        agent._run_maturity = "AUTONOMOUS"
        assert agent._custom_action_visible("weird_floor") is False

    @pytest.mark.asyncio
    async def test_react_step_lists_custom_actions(self):
        agent = _build_agent(_agent_model())
        agent._run_maturity = "AUTONOMOUS"
        agent._custom_action_specs["custom.tool"] = {
            "description": "custom tool desc",
            "min_maturity": None,
        }
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        agent.llm.generate_structured = AsyncMock(
            return_value=ReActStep(thought="t", final_answer="answer")
        )
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        step = await agent._react_step("task", {"experiences": [], "knowledge": [], "formulas": [], "business_facts": []}, "")
        assert step.final_answer == "answer"
        prompt = agent.llm.generate_structured.await_args.kwargs["system_instruction"]
        assert "custom.tool" in prompt
        assert "custom tool desc" in prompt

    @pytest.mark.asyncio
    async def test_step_act_custom_action_sync_async_and_error(self):
        agent = _build_agent(_agent_model())

        def sync_handler(args, context):
            return "sync-ok"

        async def async_handler(args, context):
            return "async-ok"

        def broken_handler(args, context):
            raise RuntimeError("boom")

        await agent.register_action("custom.sync", sync_handler)
        await agent.register_action("custom.async", async_handler)
        await agent.register_action("custom.broken", broken_handler)

        assert await agent._step_act("custom.sync", {"a": 1}, {}) == "sync-ok"
        assert await agent._step_act("custom.async", {}, {}) == "async-ok"
        out = await agent._step_act("custom.broken", {}, {})
        assert out.startswith("Error: Custom action 'custom.broken' failed:")


class TestGenericAgentOracleTimeout:
    @pytest.mark.asyncio
    async def test_timeout_oracle_postcondition_met(self):
        agent = _build_agent(_agent_model())
        agent.mcp.call_tool = AsyncMock(side_effect=TimeoutError("timeout exceeded"))
        cm = MagicMock()
        cm.__enter__.return_value = MagicMock()
        with patch("core.database.get_db_session", return_value=cm), patch(
            "core.oracle.verify_before_retry", new=AsyncMock(return_value=True)
        ):
            out = await agent._step_act("some_tool", {"x": 1}, pre_approved=True)
        assert "Do NOT retry" in out
        assert "postcondition is already met" in out

    @pytest.mark.asyncio
    async def test_timeout_oracle_skipped_on_error(self):
        agent = _build_agent(_agent_model())
        agent.mcp.call_tool = AsyncMock(side_effect=TimeoutError("timeout exceeded"))
        with patch("core.database.get_db_session", return_value=MagicMock()), patch(
            "core.oracle.verify_before_retry",
            new=AsyncMock(side_effect=RuntimeError("oracle boom")),
        ):
            out = await agent._step_act("some_tool", {"x": 1}, pre_approved=True)
        assert "timed out" in out
        assert "You may try once more" in out
