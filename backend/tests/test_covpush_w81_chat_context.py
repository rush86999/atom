"""Coverage wave 81 — core/chat_context_manager.py (0% → ~100%).

Direct unit tests with a fully mocked LanceDB handler: resolve_reference
(no-db / no-session / no-table / no-results / workflow-id metadata / entities
dict / untyped first-entity / parse-error tolerance / exception tolerance),
get_recent_context (empty history, formatting, 200-char truncation),
store_workflow_context (with/without execution_id) and the module helpers.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

import core.chat_context_manager as ccm
from core.chat_context_manager import ChatContextManager


class FakeFrame:
    """Minimal pandas-DataFrame stand-in: len + sort_values + iterrows."""

    def __init__(self, rows):
        self.rows = rows

    def __len__(self):
        return len(self.rows)

    def sort_values(self, _col, ascending=True):
        self.rows = sorted(self.rows,
                           key=lambda r: r["created_at"], reverse=True)
        return self

    def iterrows(self):
        return iter([(i, r) for i, r in enumerate(self.rows)])


def make_rows(entries):
    """entries: list of (id, created_at, metadata_json_or_None)."""
    return FakeFrame([{
        "id": eid,
        "created_at": ts,
        "metadata": meta if meta is not None else "",
    } for eid, ts, meta in entries])


def make_table(rows=None):
    table = MagicMock()
    table.search = Mock(return_value=table)
    table.where = Mock(return_value=table)
    table.limit = Mock(return_value=table)
    table.to_pandas = Mock(return_value=make_rows([]) if rows is None else rows)
    return table


@pytest.fixture
def handler():
    h = Mock()
    h.get_table = Mock(return_value=None)
    return h


@pytest.fixture
def manager(handler):
    return ChatContextManager(lancedb_handler=handler)


class TestResolveReference:
    @pytest.mark.asyncio
    async def test_no_db_returns_none(self):
        with patch("core.chat_context_manager.get_lancedb_handler",
                   return_value=None):
            m = ChatContextManager(lancedb_handler=None)
        assert m.db is None
        assert await m.resolve_reference("text", "s1") is None

    @pytest.mark.asyncio
    async def test_no_session_returns_none(self, manager):
        assert await manager.resolve_reference("text", None) is None
        assert await manager.resolve_reference("text", "") is None

    @pytest.mark.asyncio
    async def test_no_table_returns_none(self, manager, handler):
        handler.get_table.return_value = None
        assert await manager.resolve_reference("text", "s1") is None
        handler.get_table.assert_called_once_with("chat_messages")

    @pytest.mark.asyncio
    async def test_no_results_returns_none(self, manager, handler):
        table = make_table()
        handler.get_table.return_value = table
        assert await manager.resolve_reference("text", "s1") is None

    @pytest.mark.asyncio
    async def test_workflow_id_in_metadata(self, manager, handler):
        table = make_table(make_rows([(
            "m1", "2026-08-01", '{"workflow_id": "wf-9", "workflow_name": "Sales"}')]))
        handler.get_table.return_value = table
        result = await manager.resolve_reference("that workflow", "s1",
                                                 entity_type="workflow")
        assert result == {"type": "workflow", "id": "wf-9", "name": "Sales"}

    @pytest.mark.asyncio
    async def test_entity_id_in_entities_dict(self, manager, handler):
        table = make_table(make_rows([(
            "m1", "2026-08-01",
            '{"entities": {"task_id": "t-7", "task_name": "Ship docs"}}')]))
        handler.get_table.return_value = table
        result = await manager.resolve_reference("that task", "s1",
                                                 entity_type="task")
        assert result == {"type": "task", "id": "t-7", "name": "Ship docs"}

    @pytest.mark.asyncio
    async def test_untyped_returns_first_workflow(self, manager, handler):
        table = make_table(make_rows([(
            "m1", "2026-08-01",
            '{"entities": {"workflow_id": "wf-3", "workflow_name": "Onboard"}}')]))
        handler.get_table.return_value = table
        result = await manager.resolve_reference("it", "s1")
        assert result == {"type": "workflow", "id": "wf-3", "name": "Onboard"}

    @pytest.mark.asyncio
    async def test_untyped_metadata_workflow(self, manager, handler):
        table = make_table(make_rows([(
            "m1", "2026-08-01", '{"workflow_id": "wf-4"}')]))
        handler.get_table.return_value = table
        result = await manager.resolve_reference("it", "s1")
        assert result == {"type": "workflow", "id": "wf-4", "name": None}

    @pytest.mark.asyncio
    async def test_newest_first_and_parse_error_continues(self, manager, handler):
        # newest row (bad JSON) is processed first → parse error caught, then
        # the older valid rows resolve the workflow
        table = make_table(make_rows([
            ("m1", "2026-08-05", "{not json"),
            ("m2", "2026-08-03", '{"workflow_id": "wf-5"}'),
            ("m3", "2026-08-02", '{"entities": {"workflow_id": "wf-2"}}'),
        ]))
        handler.get_table.return_value = table
        result = await manager.resolve_reference("it", "s1")
        assert result == {"type": "workflow", "id": "wf-5", "name": None}

    @pytest.mark.asyncio
    async def test_malformed_row_metadata_is_empty_dict(self, manager, handler):
        table = make_table(make_rows([("m1", "2026-08-01", None)]))
        handler.get_table.return_value = table
        assert await manager.resolve_reference("it", "s1") is None

    @pytest.mark.asyncio
    async def test_no_matching_entity_returns_none(self, manager, handler):
        table = make_table(make_rows([
            ("m1", "2026-08-01", '{"entities": {"task_id": "t-1"}}')]))
        handler.get_table.return_value = table
        result = await manager.resolve_reference("that workflow", "s1",
                                                 entity_type="workflow")
        assert result is None

    @pytest.mark.asyncio
    async def test_search_error_returns_none(self, manager, handler):
        table = MagicMock()
        table.search = Mock(side_effect=RuntimeError("lancedb down"))
        handler.get_table.return_value = table
        assert await manager.resolve_reference("it", "s1") is None

    @pytest.mark.asyncio
    async def test_get_table_error_returns_none(self, manager, handler):
        handler.get_table = Mock(side_effect=RuntimeError("boom"))
        assert await manager.resolve_reference("it", "s1") is None


class TestGetRecentContext:
    @pytest.mark.asyncio
    async def test_no_messages_returns_empty(self, manager):
        chat = Mock()
        chat.get_session_history = Mock(return_value=[])
        with patch("core.lancedb_handler.get_chat_history_manager", return_value=chat):
            result = await manager.get_recent_context("s1", "ws1")
        assert result == ""
        chat.get_session_history.assert_called_once_with("s1", limit=5)

    @pytest.mark.asyncio
    async def test_formats_messages(self, manager):
        chat = Mock()
        chat.get_session_history = Mock(return_value=[
            {"role": "user", "text": "hello"},
            {"role": "assistant", "text": "hi there"},
        ])
        with patch("core.lancedb_handler.get_chat_history_manager", return_value=chat):
            result = await manager.get_recent_context("s1", "ws1", limit=2)
        assert result == "User: hello\nAssistant: hi there"

    @pytest.mark.asyncio
    async def test_truncates_long_content(self, manager):
        chat = Mock()
        chat.get_session_history = Mock(return_value=[
            {"role": "user", "text": "x" * 250},
        ])
        with patch("core.lancedb_handler.get_chat_history_manager", return_value=chat):
            result = await manager.get_recent_context("s1")
        assert result == "User: " + "x" * 197 + "..."
        assert len(result) < 210

    @pytest.mark.asyncio
    async def test_unknown_role_and_missing_text(self, manager):
        chat = Mock()
        chat.get_session_history = Mock(return_value=[
            {"text": "no role"},
        ])
        with patch("core.lancedb_handler.get_chat_history_manager", return_value=chat):
            result = await manager.get_recent_context("s1")
        assert result == "Unknown: no role"


class TestStoreWorkflowContext:
    @pytest.mark.asyncio
    async def test_with_execution_id(self, manager):
        chat = Mock()
        chat.save_message = Mock(return_value=True)
        with patch("core.lancedb_handler.get_chat_history_manager", return_value=chat):
            ok = await manager.store_workflow_context(
                "s1", "u1", "ws1", "wf-1", "Sales", execution_id="ex-1",
                status="completed")
        assert ok is True
        kwargs = chat.save_message.call_args[1]
        assert kwargs["session_id"] == "s1"
        assert kwargs["user_id"] == "u1"
        assert kwargs["role"] == "system"
        assert "Sales" in kwargs["content"] and "ex-1" in kwargs["content"]
        assert kwargs["metadata"]["type"] == "workflow_execution"
        assert kwargs["metadata"]["execution_id"] == "ex-1"

    @pytest.mark.asyncio
    async def test_without_execution_id(self, manager):
        chat = Mock()
        chat.save_message = Mock(return_value=False)
        with patch("core.lancedb_handler.get_chat_history_manager", return_value=chat):
            ok = await manager.store_workflow_context(
                "s1", "u1", "ws1", "wf-1", "Sales")
        assert ok is False
        content = chat.save_message.call_args[1]["content"]
        assert "Execution ID" not in content
        assert chat.save_message.call_args[1]["metadata"]["execution_id"] is None


class TestHelpers:
    def test_get_chat_context_manager_delegates(self):
        sentinel = object()
        with patch("core.lancedb_handler.get_chat_context_manager",
                   return_value=sentinel) as m:
            assert ccm.get_chat_context_manager("ws9") is sentinel
        m.assert_called_once_with("ws9")

    def test_constructor_default_handler(self):
        handler = object()
        with patch("core.chat_context_manager.get_lancedb_handler",
                   return_value=handler):
            m = ChatContextManager()
        assert m.db is handler

    def test_constructor_explicit_handler(self):
        h = object()
        assert ChatContextManager(lancedb_handler=h).db is h
