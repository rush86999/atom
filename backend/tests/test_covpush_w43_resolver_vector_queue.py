"""Coverage wave 43 — capability_resolver (67%), turn_fact_vector_store (47%), turn_fact_queue (0%) → 90%+.

- resolver: string caps normalization, TypeError tolerance, is_tool_allowed
  (non-str/dotted registered-unregistered/exception), agent-from-context paths
- vector store: handler-unavailable, per-row write success/failure, search
  (short query / empty results / dict+object ids / exception)
- queue: enqueue gates (flag/prompt/queue-full), worker lifecycle (idempotent,
  closed loop, no-loop deferral), drain_once, stats, worker exception
  tolerance + cancellation, _process success/exception, singleton
"""
import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.capability_resolver import (
    UNRESTRICTED,
    get_agent_for_context,
    is_tool_allowed,
    resolve_allowed_tools,
)
from core.turn_fact_queue import ExtractionQueue, get_extraction_queue
from core.turn_fact_vector_store import (
    search_relevant_fact_ids,
    write_turn_fact_vectors,
)


def await_coroutine(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ============================================================================
# capability_resolver
# ============================================================================

class TestNormalizeCapabilities:
    def test_string_caps_wrapped(self):
        agent = SimpleNamespace(capabilities="chat")
        allowed = resolve_allowed_tools(agent, tier="autonomous")
        assert allowed == ("chat",)

    def test_type_error_falls_back_unrestricted(self):
        agent = SimpleNamespace(capabilities=12345)
        allowed = resolve_allowed_tools(agent, tier="autonomous")
        assert allowed == UNRESTRICTED

    def test_blank_entries_stripped(self):
        agent = SimpleNamespace(capabilities=["a", "", "b"])
        allowed = resolve_allowed_tools(agent, tier="autonomous")
        assert allowed == ("a", "b")

    def test_wildcard_in_list_unrestricted(self):
        agent = SimpleNamespace(capabilities=["*", "a"])
        assert resolve_allowed_tools(agent, tier="autonomous") == UNRESTRICTED


class TestResolveAllowedTools:
    def _agent(self, caps):
        return SimpleNamespace(capabilities=caps, status="intern")

    def test_tier_from_agent_status(self):
        agent = self._agent(["canvas_render"])
        allowed = resolve_allowed_tools(agent, tier=None)
        # intern floor includes canvas_render; caps ∩ floor = (canvas_render,)
        assert "canvas_render" in allowed

    def test_unknown_tier_falls_back_student_floor(self):
        agent = self._agent(["canvas_render"])
        allowed = resolve_allowed_tools(agent, tier="bogus-tier")
        assert allowed == ("canvas_render",)  # canvas_render is in student floor

    def test_intersection_narrows_below_floor(self):
        agent = self._agent(["canvas_render", "browser_click", "not_a_tool"])
        allowed = resolve_allowed_tools(agent, tier="student")
        assert "canvas_render" in allowed
        assert "not_a_tool" not in allowed
        assert "browser_click" not in allowed  # above student floor

    def test_unrestricted_caps_bounded_by_floor(self):
        agent = self._agent(None)
        allowed = resolve_allowed_tools(agent, tier="intern")
        assert allowed != UNRESTRICTED
        assert len(allowed) > 0


class TestIsToolAllowed:
    def test_non_string_tool_rejected(self):
        assert is_tool_allowed(("a",), 123) is False

    def test_unrestricted_allows_anything(self):
        assert is_tool_allowed(UNRESTRICTED, "anything") is True

    def test_membership_exact(self):
        assert is_tool_allowed(("documents.search",), "documents.search") is True
        assert is_tool_allowed(("a",), "b") is False

    def test_dotted_registered_action_allowed(self):
        with patch("core.action_registry.action_registry") as reg:
            reg.get_action.return_value = SimpleNamespace()
            assert is_tool_allowed(("a",), "documents.search") is True
            reg.get_action.assert_called_once_with("documents.search")

    def test_dotted_unregistered_rejected(self):
        with patch("core.action_registry.action_registry") as reg:
            reg.get_action.return_value = None
            assert is_tool_allowed(("a",), "evil.tool") is False

    def test_dotted_registry_error_rejected(self):
        with patch("core.action_registry.action_registry") as reg:
            reg.get_action.side_effect = RuntimeError("boom")
            assert is_tool_allowed(("a",), "evil.tool") is False

    def test_empty_allowed_denies_all(self):
        assert is_tool_allowed((), "x") is False


class TestGetAgentForContext:
    def test_no_context(self):
        assert get_agent_for_context(None) is None

    def test_no_agent_id(self):
        assert get_agent_for_context({}) is None
        assert get_agent_for_context({"workspace_id": "w1"}) is None

    def test_db_exception_returns_none(self):
        with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            assert get_agent_for_context({"agent_id": "a1"}) is None

    def test_success_returns_agent(self):
        agent = SimpleNamespace(id="a1")
        with patch("core.database.get_db_session") as gds:
            db = gds.return_value.__enter__.return_value
            db.query.return_value.filter.return_value.first.return_value = agent
            assert get_agent_for_context({"agent_id": "a1"}) is agent


# ============================================================================
# turn_fact_vector_store
# ============================================================================

class TestVectorStore:
    def _row(self, **kw):
        base = dict(
            id="f1", fact_text="text", category="exact_value", domain="general",
            confidence=0.8, content_hash="h", extraction_source="turn",
            user_id="u1", workspace_id="ws1",
        )
        base.update(kw)
        return SimpleNamespace(**base)

    def test_handler_unavailable_write_returns_zero(self):
        with patch("core.lancedb_handler.LanceDBHandler", side_effect=RuntimeError("no lancedb")):
            assert write_turn_fact_vectors(rows=[self._row()]) == 0

    def test_handler_unavailable_search_returns_empty(self):
        with patch("core.lancedb_handler.LanceDBHandler", side_effect=RuntimeError("no lancedb")):
            assert search_relevant_fact_ids(workspace_id="ws1", query="hello world") == []

    def test_short_query_returns_empty(self):
        handler = MagicMock()
        with patch("core.lancedb_handler.LanceDBHandler", return_value=handler):
            assert search_relevant_fact_ids(workspace_id="ws1", query="hi") == []
            handler.search.assert_not_called()

    def test_write_counts_successes_and_skips_failures(self):
        handler = MagicMock()
        handler.add_document.side_effect = [True, RuntimeError("boom")]
        with patch("core.lancedb_handler.LanceDBHandler", return_value=handler):
            written = write_turn_fact_vectors(
                rows=[self._row(id="f1"), self._row(id="f2")])
        assert written == 1
        assert handler.add_document.call_count == 2

    def test_write_uses_metadata(self):
        handler = MagicMock()
        handler.add_document.return_value = True
        with patch("core.lancedb_handler.LanceDBHandler", return_value=handler):
            write_turn_fact_vectors(rows=[self._row()], source_text="src")
        _, kwargs = handler.add_document.call_args
        assert kwargs["table_name"] == "turn_facts"
        assert kwargs["doc_id"] == "f1"
        assert "extract_knowledge" not in kwargs  # dead param removed (R84)
        assert kwargs["metadata"]["category"] == "exact_value"

    def test_search_empty_results(self):
        handler = MagicMock()
        handler.search.return_value = []
        with patch("core.lancedb_handler.LanceDBHandler", return_value=handler):
            assert search_relevant_fact_ids(workspace_id="ws1", query="hello world") == []

    def test_search_dict_and_object_results(self):
        handler = MagicMock()
        handler.search.return_value = [{"id": "f1"}, SimpleNamespace(id="f2"), {"no_id": 1}]
        with patch("core.lancedb_handler.LanceDBHandler", return_value=handler):
            ids = search_relevant_fact_ids(workspace_id="ws1", query="hello world")
        assert ids == ["f1", "f2"]

    def test_search_exception_returns_empty(self):
        handler = MagicMock()
        handler.search.side_effect = RuntimeError("boom")
        with patch("core.lancedb_handler.LanceDBHandler", return_value=handler):
            assert search_relevant_fact_ids(workspace_id="ws1", query="hello world") == []


# ============================================================================
# turn_fact_queue
# ============================================================================

class TestExtractionQueue:
    async def test_enqueue_disabled_flag(self):
        q = ExtractionQueue()
        with patch("core.turn_fact_queue.TURN_FACT_PRE_COMPRESS_ENABLED", False):
            assert q.enqueue("p", "ws1") is False

    async def test_enqueue_empty_prompt_or_workspace(self):
        q = ExtractionQueue()
        assert q.enqueue("", "ws1") is False
        assert q.enqueue("p", "") is False

    async def test_enqueue_success_and_stats(self):
        q = ExtractionQueue()
        assert q.enqueue("p", "ws1", execution_id="e1", session_id="s1") is True
        stats = q.stats()
        assert stats["queued"] == 1
        assert stats["worker_started"] is False

    async def test_enqueue_queue_full_dropped(self):
        q = ExtractionQueue(maxsize=1)
        q.enqueue("p1", "ws1")
        assert q.enqueue("p2", "ws1") is False
        assert q.stats()["dropped"] == 1

    async def test_drain_once_empty(self):
        q = ExtractionQueue()
        assert await q.drain_once() == 0

    async def test_drain_once_processes_item(self):
        q = ExtractionQueue()
        q.enqueue("some prompt text", "ws1")
        with patch("core.turn_fact_queue.get_turn_fact_extractor") as gtf:
            ex = gtf.return_value
            ex.extract_from_prompt_before_truncation = AsyncMock(
                return_value=[SimpleNamespace()])
            count = await q.drain_once()
        assert count == 1
        assert q.stats()["drained"] == 1

    async def test_ensure_worker_idempotent(self):
        q = ExtractionQueue()
        loop = asyncio.get_event_loop()
        with patch.object(loop, "create_task", return_value=Mock()) as ct:
            q.ensure_worker()
            q.ensure_worker()
        assert q._started is True
        assert ct.call_count == 1

    def test_ensure_worker_no_loop_deferred(self):
        q = ExtractionQueue()
        with patch("core.turn_fact_queue.asyncio.get_event_loop",
                   side_effect=RuntimeError("no loop")):
            q.ensure_worker()
        assert q._started is False

    def test_ensure_worker_closed_loop_skips(self):
        q = ExtractionQueue()
        closed = Mock()
        closed.is_closed.return_value = True
        with patch("core.turn_fact_queue.asyncio.get_event_loop", return_value=closed):
            q.ensure_worker()
        assert q._started is False
        closed.create_task.assert_not_called()

    async def test_worker_loop_processes_and_tolerates_errors(self):
        q = ExtractionQueue()
        q.enqueue("prompt a", "ws1")
        with patch.object(q, "_process", new=AsyncMock(return_value=1)) as proc:
            task = asyncio.get_event_loop().create_task(q._worker_loop())
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        proc.assert_awaited_once()

    async def test_worker_loop_survives_exception(self):
        q = ExtractionQueue()
        # _process swallows its own errors; force an exception from the loop body
        q._q.put_nowait(object())
        q._process = AsyncMock(side_effect=RuntimeError("boom"))
        task = asyncio.get_event_loop().create_task(q._worker_loop())
        await asyncio.sleep(0.15)
        assert task.done() is False  # worker kept running after the failure
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def test_process_success_and_exception(self):
        q = ExtractionQueue()
        with patch("core.turn_fact_queue.get_turn_fact_extractor") as gtf:
            ex = gtf.return_value
            ex.extract_from_prompt_before_truncation = AsyncMock(
                return_value=[SimpleNamespace(), SimpleNamespace()])
            item = SimpleNamespace(prompt="p", workspace_id="ws1", tenant_id="t1",
                                   execution_id=None, episode_id=None,
                                   session_id=None, user_id=None)
            assert await q._process(item) == 2
            ex.extract_from_prompt_before_truncation = AsyncMock(
                side_effect=RuntimeError("boom"))
            assert await q._process(item) == 0

    def test_singleton(self):
        with patch("core.turn_fact_queue._queue", None):
            q1 = get_extraction_queue()
            assert q1 is get_extraction_queue()
            assert q1.stats()["queued"] == 0
