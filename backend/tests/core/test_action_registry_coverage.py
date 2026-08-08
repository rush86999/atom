"""
Coverage + bug-hunt tests for ``core/action_registry.py``.

These tests exercise the registry core (register/get/list/execute), the
``register_action`` decorator, the ``_context_user_id`` helper, and every seed
action's happy-path + validation + error path. DB and external tool/service
imports are mocked so there is no real network or DB dependency.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core import action_registry as ar_module
from core.action_registry import (
    ActionDefinition,
    ActionNotFoundError,
    ActionRegistry,
    _context_user_id,
    action_registry,
    register_action,
)


# ---------------------------------------------------------------------------
# Registry core
# ---------------------------------------------------------------------------

class TestActionRegistryCore:
    def test_register_overwrites_existing_name(self):
        reg = ActionRegistry()

        async def h1(args, ctx):
            return "v1"

        async def h2(args, ctx):
            return "v2"

        reg.register("x", h1, description="first")
        reg.register("x", h2, description="second")
        assert len(reg.list_actions()) == 1
        # Second registration wins.
        result = asyncio.get_event_loop().run_until_complete(
            reg.execute_action("x", {}, {})
        )
        assert result == "v2"

    def test_get_action_returns_none_for_unknown(self):
        reg = ActionRegistry()
        assert reg.get_action("missing") is None

    def test_get_action_returns_definition_for_known(self):
        reg = ActionRegistry()

        async def h(args, ctx):
            return 1

        action = reg.register("known", h)
        assert reg.get_action("known") is action

    def test_get_all_definitions_returns_list_copy(self):
        reg = ActionRegistry()

        async def h(args, ctx):
            return 1

        reg.register("a", h)
        reg.register("b", h)
        defs = reg.get_all_definitions()
        # Mutating the returned list must not affect the registry.
        defs.clear()
        assert len(reg.get_all_definitions()) == 2

    def test_list_actions_sorted(self):
        reg = ActionRegistry()

        async def h(args, ctx):
            return 1

        reg.register("zeta", h)
        reg.register("alpha", h)
        reg.register("mid", h)
        assert reg.list_actions() == ["alpha", "mid", "zeta"]

    def test_list_action_names_alias(self):
        reg = ActionRegistry()

        async def h(args, ctx):
            return 1

        reg.register("only", h)
        assert reg.list_action_names() == reg.list_actions()

    @pytest.mark.asyncio
    async def test_execute_action_unknown_raises(self):
        reg = ActionRegistry()
        with pytest.raises(ActionNotFoundError):
            await reg.execute_action("nope", {}, {})

    @pytest.mark.asyncio
    async def test_execute_action_invokes_handler_with_args(self):
        reg = ActionRegistry()
        captured = {}

        async def h(args, ctx):
            captured.update(args=args, ctx=ctx)
            return "ok"

        reg.register("run", h)
        out = await reg.execute_action("run", {"a": 1}, {"b": 2})
        assert out == "ok"
        assert captured == {"args": {"a": 1}, "ctx": {"b": 2}}

    def test_action_not_found_error_is_lookup_error(self):
        # RPC route guards with `except LookupError`, so the subclass link matters.
        assert issubclass(ActionNotFoundError, LookupError)


# ---------------------------------------------------------------------------
# ActionDefinition defaults
# ---------------------------------------------------------------------------

class TestActionDefinition:
    def test_description_falls_back_to_handler_docstring(self):
        async def h(args, ctx):
            """My docstring."""
            return None

        d = ActionDefinition("n", h)
        assert d.description == "My docstring."

    def test_description_falls_back_to_default_when_no_doc(self):
        async def h(args, ctx):
            return None

        # Strip docstring to force the default path.
        h.__doc__ = None
        d = ActionDefinition("n", h)
        assert d.description == "Action n"

    def test_explicit_description_wins_over_docstring(self):
        async def h(args, ctx):
            """Ignored."""
            return None

        d = ActionDefinition("n", h, description="explicit")
        assert d.description == "explicit"

    def test_default_parameters_schema(self):
        async def h(args, ctx):
            return None

        d = ActionDefinition("n", h)
        assert d.parameters_schema == {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def test_explicit_parameters_schema_used(self):
        async def h(args, ctx):
            return None

        schema = {"type": "object", "properties": {"q": {}}, "required": ["q"]}
        d = ActionDefinition("n", h, parameters_schema=schema)
        assert d.parameters_schema is schema

    def test_repr(self):
        async def h(args, ctx):
            return None

        d = ActionDefinition("named", h)
        assert repr(d) == "<ActionDefinition named>"


# ---------------------------------------------------------------------------
# register_action decorator
# ---------------------------------------------------------------------------

class TestRegisterActionDecorator:
    def test_decorator_registers_and_returns_callable(self):
        # Use a private registry to avoid polluting the module singleton.
        target = ActionRegistry()

        with patch.object(ar_module, "action_registry", target):
            @register_action("decorated", description="d")
            async def handler(args, ctx):
                return "ran"

            # Decorator returns the original function unchanged.
            assert handler.__name__ == "handler"
            assert target.get_action("decorated") is not None
            assert target.get_action("decorated").description == "d"

    def test_decorator_passes_schema_through(self):
        target = ActionRegistry()
        schema = {"type": "object", "properties": {}, "required": []}

        with patch.object(ar_module, "action_registry", target):
            @register_action("with_schema", parameters_schema=schema)
            async def handler(args, ctx):
                return None

            assert target.get_action("with_schema").parameters_schema is schema


# ---------------------------------------------------------------------------
# _context_user_id helper
# ---------------------------------------------------------------------------

class TestContextUserId:
    def test_empty_context_returns_none(self):
        assert _context_user_id({}) is None
        assert _context_user_id(None) is None

    def test_user_id_key(self):
        assert _context_user_id({"user_id": 42}) == "42"

    def test_userId_camel_case_key(self):
        assert _context_user_id({"userId": "abc"}) == "abc"

    def test_actor_id_key(self):
        assert _context_user_id({"actor_id": "u9"}) == "u9"

    def test_falsy_values_skipped(self):
        assert _context_user_id({"user_id": 0, "userId": "", "actor_id": "x"}) == "x"

    def test_user_object_with_id(self):
        user = MagicMock()
        user.id = 7
        assert _context_user_id({"user": user}) == "7"

    def test_user_object_without_id_returns_none(self):
        user = MagicMock()
        user.id = None
        # When user.id is falsy, fall through; no other key present -> None.
        assert _context_user_id({"user": user}) is None

    def test_no_user_key_returns_none(self):
        assert _context_user_id({"other": "value"}) is None


# ---------------------------------------------------------------------------
# Seed actions — exercise the lazy-import wrappers via the singleton.
# Each test mocks the underlying tool/service so no real IO happens.
# ---------------------------------------------------------------------------

class TestDocumentsSearchAction:
    @pytest.mark.asyncio
    async def test_empty_query_returns_error(self):
        result = await action_registry.execute_action(
            "documents.search", {"query": "   "}, {}
        )
        assert result["success"] is False
        assert "query" in result["error"]
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_missing_query_returns_error(self):
        result = await action_registry.execute_action("documents.search", {}, {})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_successful_search_combines_sources(self):
        ingested_doc = MagicMock(id="i1", file_name="f.txt", content_preview="hello world")
        knowledge_doc = MagicMock(id="k1", title="kb", content="deep knowledge")

        ingested_q = MagicMock()
        ingested_q.all.return_value = [ingested_doc]
        knowledge_q = MagicMock()
        knowledge_q.all.return_value = [knowledge_doc]
        # .limit() returns the query itself so .all() resolves.
        ingested_q.limit.return_value = ingested_q
        knowledge_q.limit.return_value = knowledge_q

        db = MagicMock()
        # First .query() -> IngestedDocument, second -> KnowledgeDocument.
        db.query.side_effect = [MagicMock(filter=MagicMock(return_value=ingested_q)),
                                MagicMock(filter=MagicMock(return_value=knowledge_q))]

        ctx_manager = MagicMock()
        ctx_manager.return_value.__enter__.return_value = db
        ctx_manager.return_value.__exit__.return_value = False

        with patch("core.database.get_db_session", ctx_manager):
            result = await action_registry.execute_action(
                "documents.search", {"query": "world", "limit": 10}, {}
            )
        assert result["success"] is True
        assert result["query"] == "world"
        assert len(result["results"]) == 2
        assert result["results"][0]["source"] == "ingested"
        assert result["results"][1]["source"] == "knowledge"

    @pytest.mark.asyncio
    async def test_search_skips_knowledge_when_limit_filled(self):
        ingested_doc = MagicMock(id="i1", file_name="f", content_preview="p")
        ingested_q = MagicMock()
        ingested_q.all.return_value = [ingested_doc]
        ingested_q.limit.return_value = ingested_q

        db = MagicMock()
        db.query.return_value = MagicMock(filter=MagicMock(return_value=ingested_q))

        ctx_manager = MagicMock()
        ctx_manager.return_value.__enter__.return_value = db
        ctx_manager.return_value.__exit__.return_value = False

        with patch("core.database.get_db_session", ctx_manager):
            result = await action_registry.execute_action(
                "documents.search", {"query": "x", "limit": 1}, {}
            )
        assert result["success"] is True
        # Only one query should have been issued (ingested filled the limit).
        assert db.query.call_count == 1

    @pytest.mark.asyncio
    async def test_search_exception_returns_failure(self):
        ctx_manager = MagicMock()
        ctx_manager.return_value.__enter__.side_effect = RuntimeError("db down")
        ctx_manager.return_value.__exit__.return_value = False

        with patch("core.database.get_db_session", ctx_manager):
            result = await action_registry.execute_action(
                "documents.search", {"query": "x"}, {}
            )
        assert result["success"] is False
        assert result["error"] == "Document search failed"
        assert result["results"] == []


class TestCanvasActions:
    @pytest.mark.asyncio
    async def test_canvas_read_missing_id(self):
        result = await action_registry.execute_action("canvas.read", {}, {})
        assert result["success"] is False
        assert "canvas_id" in result["error"]

    @pytest.mark.asyncio
    async def test_canvas_read_missing_user(self):
        result = await action_registry.execute_action(
            "canvas.read", {"canvas_id": "c1"}, {}
        )
        assert result["success"] is False
        assert "user" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_canvas_read_dispatches(self):
        with patch("tools.canvas_crud_tool.read_canvas", new=AsyncMock(return_value={"success": True, "id": "c1"})) as m:
            result = await action_registry.execute_action(
                "canvas.read", {"canvas_id": "c1"}, {"user_id": "u1"}
            )
        assert result == {"success": True, "id": "c1"}
        m.assert_awaited_once_with("u1", "c1")

    @pytest.mark.asyncio
    async def test_canvas_update_missing_id(self):
        result = await action_registry.execute_action(
            "canvas.update", {"content": {"x": 1}}, {"user_id": "u1"}
        )
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_canvas_update_missing_content(self):
        result = await action_registry.execute_action(
            "canvas.update", {"canvas_id": "c1"}, {"user_id": "u1"}
        )
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_canvas_update_missing_user(self):
        result = await action_registry.execute_action(
            "canvas.update", {"canvas_id": "c1", "content": {}}, {}
        )
        assert result["success"] is False
        assert "user" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_canvas_update_dispatches_with_optional_fields(self):
        m = AsyncMock(return_value={"success": True})
        with patch("tools.canvas_crud_tool.update_canvas_content", new=m):
            result = await action_registry.execute_action(
                "canvas.update",
                {"canvas_id": 9, "content": {"a": 1}, "canvas_type": "report", "title": "T"},
                {"user_id": "u1"},
            )
        assert result["success"] is True
        m.assert_awaited_once_with(
            user_id="u1", canvas_id="9", content={"a": 1},
            canvas_type="report", title="T",
        )


class TestTasksCreateAction:
    @pytest.mark.asyncio
    async def test_missing_title(self):
        result = await action_registry.execute_action(
            "tasks.create", {"board_id": "b1"}, {"user_id": "u1"}
        )
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_missing_board_id(self):
        result = await action_registry.execute_action(
            "tasks.create", {"title": "t"}, {"user_id": "u1"}
        )
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_blank_title_treated_as_missing(self):
        result = await action_registry.execute_action(
            "tasks.create", {"title": "   ", "board_id": "b1"}, {"user_id": "u1"}
        )
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_successful_create_returns_task_fields(self):
        task = MagicMock(
            id="t1", board_id="b1", column_id="col", title="T",
            description="d", status="backlog",
        )
        svc = MagicMock()
        svc.create_task.return_value = task

        ctx_manager = MagicMock()
        ctx_manager.return_value.__enter__.return_value = svc
        ctx_manager.return_value.__exit__.return_value = False

        board_service_mod = MagicMock(BoardService=MagicMock(return_value=svc))
        board_service_mod.TaskCreate = MagicMock()

        modules = {
            "core.board_service": board_service_mod,
            "core.database": MagicMock(get_db_session=ctx_manager),
        }
        with patch.dict("sys.modules", modules):
            result = await action_registry.execute_action(
                "tasks.create",
                {"title": "T", "board_id": "b1", "description": "d", "column_id": "col",
                 "priority": "high", "status": "backlog"},
                {"user_id": "u1"},
            )
        assert result["success"] is True
        assert result["task"]["id"] == "t1"
        assert result["task"]["title"] == "T"
        # create_task must be called with the resolved board_id + user_id.
        args, kwargs = svc.create_task.call_args
        assert kwargs["board_id"] == "b1"
        assert kwargs["created_by_user_id"] == "u1"

    @pytest.mark.asyncio
    async def test_create_exception_returns_failure(self):
        ctx_manager = MagicMock()
        ctx_manager.return_value.__enter__.side_effect = RuntimeError("boom")
        ctx_manager.return_value.__exit__.return_value = False

        with patch("core.database.get_db_session", ctx_manager), \
             patch("core.board_service.BoardService", create=True), \
             patch("core.board_service.TaskCreate", create=True):
            result = await action_registry.execute_action(
                "tasks.create", {"title": "T", "board_id": "b1"}, {"user_id": "u1"}
            )
        assert result["success"] is False
        assert result["error"] == "Task creation failed"


class TestAgentsListAction:
    @pytest.mark.asyncio
    async def test_list_no_category(self):
        a1 = MagicMock(id="a1", name="A", description="d", status="active",
                       category="ops", capabilities=["x"])
        a2 = MagicMock(id="a2", name="B", description=None, status="active",
                       category="ops", capabilities=None)
        q = MagicMock()
        # No category -> filter not applied; .all() returns both.
        q.all.return_value = [a1, a2]
        db = MagicMock()
        db.query.return_value = q

        ctx_manager = MagicMock()
        ctx_manager.return_value.__enter__.return_value = db
        ctx_manager.return_value.__exit__.return_value = False

        with patch("core.database.get_db_session", ctx_manager):
            result = await action_registry.execute_action("agents.list", {}, {})
        assert result["success"] is True
        assert len(result["agents"]) == 2
        # capabilities None coerced to []
        assert result["agents"][1]["capabilities"] == []

    @pytest.mark.asyncio
    async def test_list_with_category_filter(self):
        q = MagicMock()
        q.filter.return_value.all.return_value = []
        db = MagicMock()
        db.query.return_value = q

        ctx_manager = MagicMock()
        ctx_manager.return_value.__enter__.return_value = db
        ctx_manager.return_value.__exit__.return_value = False

        with patch("core.database.get_db_session", ctx_manager):
            result = await action_registry.execute_action(
                "agents.list", {"category": "ops"}, {}
            )
        assert result["success"] is True
        assert result["agents"] == []
        q.filter.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_exception_returns_failure(self):
        ctx_manager = MagicMock()
        ctx_manager.return_value.__enter__.side_effect = RuntimeError("db")
        ctx_manager.return_value.__exit__.return_value = False

        with patch("core.database.get_db_session", ctx_manager):
            result = await action_registry.execute_action("agents.list", {}, {})
        assert result["success"] is False
        assert result["error"] == "Agent listing failed"
        assert result["agents"] == []


# ---------------------------------------------------------------------------
# Mini-app seed actions — each just delegates to tools.mini_app_tool.<fn>,
# so we mock the target function and assert pass-through.
# ---------------------------------------------------------------------------

MINI_APP_THIN_WRAPPERS = [
    ("mini_app_scaffold", "mini_app_scaffold"),
    ("mini_app_write_logic", "mini_app_write_logic"),
    ("mini_app_dev_run", "mini_app_dev_run"),
    ("mini_app_publish", "mini_app_publish"),
    ("mini_app_install", "mini_app_install"),
    ("mini_app_run", "mini_app_run"),
    ("mini_app_list", "mini_app_list"),
    ("mini_app_get_state", "mini_app_get_state"),
    ("mini_app_set_tests", "mini_app_set_tests"),
    ("mini_app_run_tests", "mini_app_run_tests"),
    ("mini_app_logic_history", "mini_app_logic_history"),
    ("mini_app_revert_logic", "mini_app_revert_logic"),
    ("mini_app_status", "mini_app_status"),
    ("mini_app_db_query", "mini_app_db_query"),
    ("mini_app_db_write", "mini_app_db_write"),
]


@pytest.mark.parametrize("action_name,tool_fn_name", MINI_APP_THIN_WRAPPERS)
@pytest.mark.asyncio
async def test_mini_app_thin_wrapper_passes_args_and_context(action_name, tool_fn_name):
    """Every mini-app seed action should forward (args, context) to its tool."""
    sentinel = {"success": True, "from": tool_fn_name}
    mock_fn = AsyncMock(return_value=sentinel)
    with patch(f"tools.mini_app_tool.{tool_fn_name}", new=mock_fn):
        result = await action_registry.execute_action(
            action_name, {"app_id": "a1"}, {"user_id": "u1"}
        )
    assert result is sentinel
    mock_fn.assert_awaited_once_with({"app_id": "a1"}, {"user_id": "u1"})


def test_singleton_has_expected_seed_actions_registered():
    """The module-level singleton must expose all seed actions at import time."""
    names = set(action_registry.list_actions())
    expected = {
        "documents.search", "canvas.read", "canvas.update",
        "tasks.create", "agents.list",
        "mini_app_scaffold", "mini_app_write_logic", "mini_app_dev_run",
        "mini_app_publish", "mini_app_install", "mini_app_run", "mini_app_list",
        "mini_app_get_state", "mini_app_set_tests", "mini_app_run_tests",
        "mini_app_logic_history", "mini_app_revert_logic", "mini_app_status",
        "mini_app_db_query", "mini_app_db_write",
    }
    missing = expected - names
    assert not missing, f"Missing seed actions: {missing}"
