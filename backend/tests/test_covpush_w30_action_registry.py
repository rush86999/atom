"""Coverage wave 30 — core/action_registry remaining surface (78% → 95%+).

Picks up where wave 9b (documents VFS actions) left off:
- registry basics: register/get/get_all/list/list_action_names, unregister
- execute_action: found (args/context pass-through), not-found raises
- _context_user_id: empty context, each key variant, user object
- documents.search: missing query, legacy flag-off path, hybrid exception
- canvas.read/update: missing canvas_id, missing user_id, success (mocked)
- tasks.create: validation error, success (BoardService mocked), exception
- agents.list: success, category filter, exception
- mini_app_* delegates: each delegates to tools.mini_app_tool (mocked)
"""
import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.action_registry import (
    ActionNotFoundError,
    ActionRegistry,
    action_registry,
    register_action,
)


@pytest.fixture
def registry():
    return ActionRegistry()


class TestRegistryBasics:
    def test_register_and_get(self, registry):
        async def handler(args, context):
            return "ok"

        registry.register("act_1", handler, "desc", {"properties": {}})
        action = registry.get_action("act_1")
        assert action.name == "act_1"
        assert action.description == "desc"
        assert registry.get_action("missing") is None

    def test_register_returns_action(self, registry):
        async def handler(args, context):
            return "ok"

        result = registry.register("act_2", handler, "d", {})
        assert result.name == "act_2"

    def test_get_all_and_list(self, registry):
        async def h(args, context):
            return "ok"

        registry.register("b_action", h, "d", {})
        registry.register("a_action", h, "d", {})
        assert len(registry.get_all_definitions()) == 2
        assert registry.list_actions() == ["a_action", "b_action"]
        assert registry.list_action_names() == ["a_action", "b_action"]

    def test_unregister_unsupported(self, registry):
        # ActionRegistry has no unregister (actions are static definitions);
        # verify unknown-name delete semantics do not exist by accident.
        async def h(args, context):
            return "ok"

        registry.register("act_3", h, "d", {})
        assert registry.get_action("act_3") is not None
        assert not hasattr(registry, "unregister")

    def test_execute_action_found(self, registry):
        async def handler(args, context):
            return {"args": args, "ctx": context}

        registry.register("echo", handler, "d", {})
        result = asyncio.run(registry.execute_action(
            "echo", {"x": 1}, {"user_id": "u1"}
        ))
        assert result == {"args": {"x": 1}, "ctx": {"user_id": "u1"}}

    def test_execute_action_not_found(self, registry):
        with pytest.raises(ActionNotFoundError):
            asyncio.run(registry.execute_action("nope", {}, {}))

    def test_singleton_has_actions(self):
        assert len(action_registry.list_actions()) >= 30
        assert action_registry.get_action("documents.search") is not None

    def test_register_decorator(self):
        @register_action("decorated_act", description="d", parameters_schema={})
        async def h(args, context):
            return "ok"

        assert action_registry.get_action("decorated_act") is not None
        assert asyncio.run(action_registry.execute_action("decorated_act", {}, {})) == "ok"


class TestContextUser:
    def test_empty(self):
        from core.action_registry import _context_user_id
        assert _context_user_id({}) is None
        assert _context_user_id(None) is None

    def test_key_variants(self):
        from core.action_registry import _context_user_id
        assert _context_user_id({"user_id": "u1"}) == "u1"
        assert _context_user_id({"userId": "u2"}) == "u2"
        assert _context_user_id({"actor_id": 42}) == "42"

    def test_user_object(self):
        from core.action_registry import _context_user_id
        user = MagicMock()
        user.id = "u3"
        assert _context_user_id({"user": user}) == "u3"
        assert _context_user_id({"user": MagicMock(id=None)}) is None


class TestDocumentsSearch:
    async def test_missing_query(self):
        result = await action_registry.execute_action(
            "documents.search", {}, {}
        )
        assert result["success"] is False
        assert "query is required" in result["error"]

    async def test_legacy_flag_off(self):
        with patch("core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=False), \
             patch("core.action_registry._documents_search_legacy", new=AsyncMock(
                 return_value={"success": True, "legacy": True}
             )) as legacy:
            result = await action_registry.execute_action(
                "documents.search", {"query": "hello"}, {}
            )
        assert result["legacy"] is True
        legacy.assert_awaited_once()

    async def test_hybrid_exception(self):
        with patch("core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True), \
             patch("core.hybrid_search.documents_hybrid.DocumentsHybridSearch") as dcls:
            dcls.return_value.search = AsyncMock(side_effect=RuntimeError("boom"))
            result = await action_registry.execute_action(
                "documents.search", {"query": "hello"}, {}
            )
        assert result["success"] is False
        assert result["results"] == []

    async def test_hybrid_success(self):
        with patch("core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True), \
             patch("core.hybrid_search.documents_hybrid.DocumentsHybridSearch") as dcls:
            dcls.return_value.search = AsyncMock(return_value={"success": True, "results": [{"id": "1"}]})
            result = await action_registry.execute_action(
                "documents.search",
                {"query": "hello", "limit": "5", "since": "2026-01-01",
                 "source": "Docs", "author": "Ann"},
                {},
            )
        assert result["success"] is True
        assert result["results"] == [{"id": "1"}]


class TestCanvasActions:
    async def test_read_missing_canvas_id(self):
        result = await action_registry.execute_action("canvas.read", {}, {})
        assert result["success"] is False
        assert "canvas_id is required" in result["error"]

    async def test_read_missing_user(self):
        result = await action_registry.execute_action(
            "canvas.read", {"canvas_id": "c1"}, {}
        )
        assert result["success"] is False
        assert "Authenticated user" in result["error"]

    async def test_read_success(self):
        with patch("tools.canvas_crud_tool.read_canvas", new=AsyncMock(
            return_value={"success": True, "canvas": {"id": "c1"}}
        )) as rc:
            result = await action_registry.execute_action(
                "canvas.read", {"canvas_id": "c1"}, {"user_id": "u1"}
            )
        assert result["canvas"]["id"] == "c1"
        rc.assert_awaited_once_with("u1", "c1")

    async def test_update_missing_fields(self):
        result = await action_registry.execute_action("canvas.update", {"canvas_id": "c1"}, {})
        assert result["success"] is False
        result2 = await action_registry.execute_action("canvas.update", {}, {})
        assert result2["success"] is False

    async def test_update_success(self):
        with patch("tools.canvas_crud_tool.update_canvas_content", new=AsyncMock(
            return_value={"success": True}
        )) as uc:
            result = await action_registry.execute_action(
                "canvas.update",
                {"canvas_id": "c1", "content": "x", "canvas_type": "docs"},
                {"user_id": "u1"},
            )
        assert result["success"] is True
        uc.assert_awaited_once()
        kwargs = uc.await_args.kwargs
        assert kwargs["user_id"] == "u1"
        assert kwargs["canvas_type"] == "docs"


class TestTasksAndAgents:
    async def test_tasks_create_validation(self):
        result = await action_registry.execute_action("tasks.create", {}, {})
        assert result["success"] is False
        assert "title and board_id are required" in result["error"]

    async def test_tasks_create_success(self):
        with patch("core.database.get_db_session") as gds:
            db = MagicMock()
            gds.return_value.__enter__.return_value = db
            with patch("core.board_service.BoardService") as bcls:
                svc = bcls.return_value
                task = MagicMock()
                task.id = "t1"
                task.board_id = "b1"
                task.column_id = "c1"
                task.title = "Title"
                task.description = "D"
                task.status = "backlog"
                svc.create_task.return_value = task
                result = await action_registry.execute_action(
                    "tasks.create",
                    {"title": "Title", "board_id": "b1", "priority": "high"},
                    {"user_id": "u1"},
                )
        assert result["success"] is True
        assert result["task"]["id"] == "t1"

    async def test_tasks_create_exception(self):
        with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            result = await action_registry.execute_action(
                "tasks.create", {"title": "T", "board_id": "b1"}, {}
            )
        assert result["success"] is False
        assert "Task creation failed" in result["error"]

    async def test_agents_list_success_and_filter(self):
        with patch("core.database.get_db_session") as gds:
            db = MagicMock()
            gds.return_value.__enter__.return_value = db
            q = MagicMock()
            q.filter.return_value = q
            agent = MagicMock()
            agent.id = "a1"
            agent.name = "Agent"
            agent.description = "d"
            agent.status = "active"
            agent.category = "finance"
            agent.capabilities = ["read"]
            q.all.return_value = [agent]
            db.query.return_value = q
            result = await action_registry.execute_action(
                "agents.list", {"category": "finance"}, {}
            )
        assert result["success"] is True
        assert result["agents"][0]["id"] == "a1"
        q.filter.assert_called_once()

    async def test_agents_list_exception(self):
        with patch("core.database.get_db_session", side_effect=RuntimeError("down")):
            result = await action_registry.execute_action("agents.list", {}, {})
        assert result["success"] is False
        assert result["agents"] == []


class TestMiniAppDelegates:
    """Each mini_app_* action delegates to tools.mini_app_tool — verify wiring."""

    @pytest.mark.parametrize("name,fn", [
        ("mini_app_scaffold", "mini_app_scaffold"),
        ("mini_app_write_logic", "mini_app_write_logic"),
        ("mini_app_dev_run", "mini_app_dev_run"),
        ("mini_app_publish", "mini_app_publish"),
        ("mini_app_install", "mini_app_install"),
        ("mini_app_run", "mini_app_run"),
        ("mini_app_list", "mini_app_list"),
        ("mini_app_get_state", "mini_app_get_state"),
        ("mini_app_db_query", "mini_app_db_query"),
        ("mini_app_db_write", "mini_app_db_write"),
        ("mini_app_set_tests", "mini_app_set_tests"),
        ("mini_app_run_tests", "mini_app_run_tests"),
        ("mini_app_logic_history", "mini_app_logic_history"),
        ("mini_app_revert_logic", "mini_app_revert_logic"),
    ])
    def test_delegate_wiring(self, name, fn):
        with patch(f"tools.mini_app_tool.{fn}", new=AsyncMock(
            return_value={"success": True, "action": name}
        )) as mock_fn:
            result = asyncio.run(action_registry.execute_action(
                name, {"canvas_id": "c1"}, {"user_id": "u1"}
            ))
        assert result["success"] is True
        assert result["action"] == name
        mock_fn.assert_awaited_once()
