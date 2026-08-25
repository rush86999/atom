"""Coverage wave 67b — turn_fact queue/vector-store/categories + P3 gatekeeper config + error_handlers → >=95%.

Standalone file (final probe runs only this file), so every branch of the 5
target modules is exercised here:

- ``core.turn_fact_queue``: enqueue gates (flag/prompt/workspace/queue-full),
  worker lifecycle (idempotent start, closed loop, no-loop deferral), drain_once,
  stats, worker exception tolerance + cancellation, _process success/exception,
  singleton + TURN_FACT_QUEUE_MAXSIZE env.
- ``core.turn_fact_vector_store``: handler-unavailable write/search, short-query
  gate, per-row success/failure counting, metadata kwargs (user_id fallback),
  empty/dict/object results, quote escaping + empty-workspace filter, exception
  tolerance.
- ``core.turn_fact_categories``: all 5 enum members, value construction, invalid
  value, ALL_FACT_CATEGORIES.
- ``middleware.governance_middleware`` (the real P3 gatekeeper-config module —
  ``core/gatekeeper_config.py`` does not exist): mask_response_fields
  (empty/list/dict/case+separator-insensitive), _get default fallbacks
  (mutations/masked_fields/require_approval_for/plain default), case-fallback
  key match, rate-limit 0 block + limiter exception skip, required_scopes
  fail-closed/present/unconfigured, taint block/allow/exception, HITL
  success-pause/empty-response/exception fail-closed, audit on every call,
  mask_response with default + custom fields, service normalization.
- ``core.error_handlers``: ErrorCode enum, ErrorResponse/ValidationErrorDetail
  models, api_error (default/custom status, request_id, details None),
  success_response, paginated_response (0 page_size, first/middle/last page),
  global_exception_handler (generic/AtomException delegation/development vs
  production), atom_exception_handler (all 5 severities + unknown severity +
  details None), handle_validation_error / handle_not_found (default + custom
  details contract) / handle_permission_denied, InvoiceError hierarchy +
  HTTP_STATUS_MAP + to_http_exception, Result pattern (ok/error/from_exception/
  unwrap/unwrap_or/map/and_then + unknown-error raise), and the
  core.exceptions ImportError fallback (module reload with blocked import).

No LLM spend, no network, no real DB — everything is mocked (SimpleNamespace
rows, MagicMock handlers/extractors, patched rate limiter + intervention
service, monkeypatched env for the reload/development branches).
"""
import asyncio
import os
import pathlib
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core import turn_fact_queue as qmod
from core import turn_fact_vector_store as vstore
from core.error_handlers import (
    ATOM_EXCEPTIONS_AVAILABLE,
    ErrorCode,
    ErrorResponse,
    HTTP_STATUS_MAP,
    InvoiceError,
    InvoiceNotFoundError,
    InvoicePricingError,
    InvoiceValidationError,
    Result,
    ValidationErrorDetail,
    api_error,
    atom_exception_handler,
    global_exception_handler,
    handle_not_found,
    handle_permission_denied,
    handle_validation_error,
    paginated_response,
    success_response,
)
from core.turn_fact_categories import ALL_FACT_CATEGORIES, FactCategory
from core.turn_fact_queue import ExtractionQueue, get_extraction_queue
from core.turn_fact_vector_store import (
    search_relevant_fact_ids,
    write_turn_fact_vectors,
)


def make_request(request_id=None, url="http://test/boom"):
    return SimpleNamespace(state=SimpleNamespace(request_id=request_id), url=url)


# ============================================================================
# turn_fact_categories
# ============================================================================

class TestFactCategories:
    def test_all_five_categories_exist_with_expected_values(self):
        assert FactCategory.EXACT_VALUE.value == "exact_value"
        assert FactCategory.HARD_CONSTRAINT.value == "hard_constraint"
        assert FactCategory.DECISION_REASON.value == "decision_reason"
        assert FactCategory.CROSS_TASK_DEP.value == "cross_task_dep"
        assert FactCategory.IMPLICIT_PREF.value == "implicit_pref"

    def test_all_categories_tuple(self):
        assert ALL_FACT_CATEGORIES == (
            "exact_value", "hard_constraint", "decision_reason",
            "cross_task_dep", "implicit_pref",
        )
        assert len(ALL_FACT_CATEGORIES) == 5

    def test_members_iteration_matches_tuple(self):
        assert tuple(c.value for c in FactCategory) == ALL_FACT_CATEGORIES

    def test_construction_from_value(self):
        assert FactCategory("exact_value") is FactCategory.EXACT_VALUE
        assert FactCategory("implicit_pref") is FactCategory.IMPLICIT_PREF

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            FactCategory("not_a_category")

    def test_str_subclass_semantics(self):
        assert isinstance(FactCategory.EXACT_VALUE, str)
        assert FactCategory.HARD_CONSTRAINT.value == "hard_constraint"
        assert FactCategory.EXACT_VALUE == "exact_value"

    def test_unknown_attribute_is_not_a_member(self):
        assert not hasattr(FactCategory, "NOT_REAL")


# ============================================================================
# turn_fact_queue
# ============================================================================

class TestQueueEnqueue:
    def test_disabled_flag_returns_false(self):
        q = ExtractionQueue()
        with patch.object(qmod, "TURN_FACT_PRE_COMPRESS_ENABLED", False):
            assert q.enqueue("prompt", "ws1") is False

    def test_empty_prompt_returns_false(self):
        q = ExtractionQueue()
        assert q.enqueue("", "ws1") is False

    def test_empty_workspace_returns_false(self):
        q = ExtractionQueue()
        assert q.enqueue("prompt", "") is False

    def test_happy_path_queues_item(self):
        q = ExtractionQueue(maxsize=5)
        assert q.enqueue(
            "prompt", "ws1", execution_id="e1", tenant_id="t1",
            episode_id="ep1", session_id="s1", user_id="u1", model="m1",
        ) is True
        assert q._q.qsize() == 1
        item = q._q.get_nowait()
        assert item.prompt == "prompt"
        assert item.workspace_id == "ws1"
        assert item.execution_id == "e1"
        assert item.tenant_id == "t1"
        assert item.episode_id == "ep1"
        assert item.session_id == "s1"
        assert item.user_id == "u1"
        assert item.model == "m1"

    def test_queue_full_drops_and_increments(self):
        q = ExtractionQueue(maxsize=2)
        assert q.enqueue("p1", "ws1") is True
        assert q.enqueue("p2", "ws1") is True
        assert q.enqueue("p3", "ws1") is False
        assert q._dropped_count == 1
        assert q.stats()["dropped"] == 1
        assert q.stats()["queued"] == 2

    def test_enqueue_never_raises_on_full(self):
        q = ExtractionQueue(maxsize=1)
        q.enqueue("p1", "ws1")
        assert q.enqueue("p2", "ws1") is False

    def test_stats_defaults(self):
        q = ExtractionQueue()
        stats = q.stats()
        assert stats == {
            "queued": 0, "drained": 0, "dropped": 0, "worker_started": False,
        }


class TestQueueWorker:
    async def test_drain_once_empty_returns_zero(self):
        q = ExtractionQueue()
        assert await q.drain_once() == 0

    async def test_drain_once_processes_item(self):
        q = ExtractionQueue()
        q.enqueue("must use Stripe", "ws1")
        with patch.object(qmod, "get_turn_fact_extractor") as gtf:
            ex = gtf.return_value
            ex.extract_from_prompt_before_truncation = AsyncMock(
                return_value=[SimpleNamespace()])
            assert await q.drain_once() == 1
        assert q.stats()["drained"] == 1

    async def test_drain_once_no_facts(self):
        q = ExtractionQueue()
        q.enqueue("plain prompt", "ws1")
        with patch.object(qmod, "get_turn_fact_extractor") as gtf:
            ex = gtf.return_value
            ex.extract_from_prompt_before_truncation = AsyncMock(return_value=[])
            assert await q.drain_once() == 0
        assert q.stats()["drained"] == 1

    async def test_worker_loop_drains_item(self):
        q = ExtractionQueue()
        q.enqueue("prompt a", "ws1")
        with patch.object(q, "_process", new=AsyncMock(return_value=1)) as proc:
            task = asyncio.get_event_loop().create_task(q._worker_loop())
            await asyncio.sleep(0.05)
            task.cancel()
            await task
        proc.assert_awaited_once()
        assert task.done()

    async def test_worker_loop_survives_exception(self):
        q = ExtractionQueue()
        q._q.put_nowait(object())
        q._process = AsyncMock(side_effect=RuntimeError("boom"))
        task = asyncio.get_event_loop().create_task(q._worker_loop())
        await asyncio.sleep(0.15)
        assert task.done() is False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert task.done()

    async def test_worker_loop_breaks_on_cancellation(self):
        q = ExtractionQueue()
        task = asyncio.get_event_loop().create_task(q._worker_loop())
        await asyncio.sleep(0.01)
        task.cancel()
        await task
        assert task.done()
        assert task.cancelled() is False


class TestQueueProcess:
    async def test_process_success_with_rows(self):
        q = ExtractionQueue()
        with patch.object(qmod, "get_turn_fact_extractor") as gtf:
            ex = gtf.return_value
            ex.extract_from_prompt_before_truncation = AsyncMock(
                return_value=[SimpleNamespace(), SimpleNamespace(), SimpleNamespace()])
            item = SimpleNamespace(
                prompt="p", workspace_id="ws1", tenant_id="t1",
                execution_id="e1", episode_id="ep1", session_id="s1", user_id="u1",
            )
            assert await q._process(item) == 3
            gtf.assert_called_once_with(workspace_id="ws1", tenant_id="t1")

    async def test_process_extractor_raises_returns_zero(self):
        q = ExtractionQueue()
        with patch.object(qmod, "get_turn_fact_extractor") as gtf:
            ex = gtf.return_value
            ex.extract_from_prompt_before_truncation = AsyncMock(
                side_effect=RuntimeError("llm down"))
            item = SimpleNamespace(
                prompt="p", workspace_id="ws1", tenant_id="t1",
                execution_id=None, episode_id=None, session_id=None, user_id=None,
            )
            assert await q._process(item) == 0

    async def test_process_get_extractor_raises_returns_zero(self):
        q = ExtractionQueue()
        with patch.object(qmod, "get_turn_fact_extractor", side_effect=RuntimeError("nope")):
            item = SimpleNamespace(
                prompt="p", workspace_id="ws1", tenant_id="t1",
                execution_id=None, episode_id=None, session_id=None, user_id=None,
            )
            assert await q._process(item) == 0


class TestQueueLifecycle:
    def test_ensure_worker_starts_once(self):
        q = ExtractionQueue()
        loop = MagicMock()
        loop.is_closed.return_value = False
        task = MagicMock()
        loop.create_task.return_value = task
        with patch.object(qmod.asyncio, "get_event_loop", return_value=loop):
            q.ensure_worker()
            q.ensure_worker()
        assert q._started is True
        assert loop.create_task.call_count == 1
        assert q.stats()["worker_started"] is True

    def test_ensure_worker_closed_loop_skips(self):
        q = ExtractionQueue()
        loop = MagicMock()
        loop.is_closed.return_value = True
        with patch.object(qmod.asyncio, "get_event_loop", return_value=loop):
            q.ensure_worker()
        assert q._started is False
        loop.create_task.assert_not_called()

    def test_ensure_worker_no_running_loop_deferred(self):
        q = ExtractionQueue()
        with patch.object(
            qmod.asyncio, "get_event_loop",
            side_effect=RuntimeError("no running event loop"),
        ):
            q.ensure_worker()
        assert q._started is False


class TestQueueSingleton:
    def test_get_extraction_queue_singleton(self):
        with patch.object(qmod, "_queue", None):
            a = get_extraction_queue()
            b = get_extraction_queue()
        assert a is b
        assert isinstance(a, ExtractionQueue)

    def test_get_extraction_queue_maxsize_from_env(self):
        with patch.object(qmod, "_queue", None), patch.dict(
            os.environ, {"TURN_FACT_QUEUE_MAXSIZE": "7"}
        ):
            q = get_extraction_queue()
        assert q._q.maxsize == 7

    def test_pending_extraction_defaults(self):
        item = qmod._PendingExtraction(prompt="p", workspace_id="ws1")
        assert item.tenant_id == "default"
        assert item.execution_id is None
        assert item.episode_id is None
        assert item.session_id is None
        assert item.user_id is None
        assert item.model is None


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

    def test_write_counts_only_true_results(self):
        handler = MagicMock()
        handler.add_document.side_effect = [True, False, RuntimeError("boom")]
        with patch("core.lancedb_handler.LanceDBHandler", return_value=handler):
            written = write_turn_fact_vectors(
                rows=[self._row(id="f1"), self._row(id="f2"), self._row(id="f3")],
                source_text="src",
            )
        assert written == 1
        assert handler.add_document.call_count == 3

    def test_write_metadata_kwargs(self):
        handler = MagicMock()
        handler.add_document.return_value = True
        with patch("core.lancedb_handler.LanceDBHandler", return_value=handler):
            write_turn_fact_vectors(rows=[self._row(id="f9")])
        _, kwargs = handler.add_document.call_args
        assert kwargs["table_name"] == "turn_facts"
        assert kwargs["text"] == "text"
        assert kwargs["source"] == "turn_fact:exact_value"
        assert kwargs["metadata"] == {
            "category": "exact_value", "domain": "general",
            "confidence": 0.8, "content_hash": "h", "extraction_source": "turn",
        }
        assert kwargs["user_id"] == "u1"
        assert kwargs["workspace_id"] == "ws1"
        assert kwargs["doc_id"] == "f9"
        assert "extract_knowledge" not in kwargs  # dead param removed (R84)
        assert kwargs["skip_ai_triggers"] is True

    def test_write_user_id_none_falls_back(self):
        handler = MagicMock()
        handler.add_document.return_value = True
        with patch("core.lancedb_handler.LanceDBHandler", return_value=handler):
            write_turn_fact_vectors(rows=[self._row(user_id=None)])
        _, kwargs = handler.add_document.call_args
        assert kwargs["user_id"] == "turn_fact"

    def test_search_short_or_missing_query_returns_empty(self):
        handler = MagicMock()
        with patch("core.lancedb_handler.LanceDBHandler", return_value=handler):
            assert search_relevant_fact_ids(workspace_id="ws1", query="hi") == []
            assert search_relevant_fact_ids(workspace_id="ws1", query="") == []
            assert search_relevant_fact_ids(workspace_id="ws1", query=None) == []
            assert search_relevant_fact_ids(workspace_id="ws1", query="  ") == []
        handler.search.assert_not_called()

    def test_search_empty_results_returns_empty(self):
        handler = MagicMock()
        handler.search.return_value = []
        with patch("core.lancedb_handler.LanceDBHandler", return_value=handler):
            assert search_relevant_fact_ids(workspace_id="ws1", query="hello world") == []

    def test_search_dict_and_object_results(self):
        handler = MagicMock()
        handler.search.return_value = [
            {"id": "f1"}, SimpleNamespace(id="f2"), {"no_id": 1},
            SimpleNamespace(id=None), {"id": ""},
        ]
        with patch("core.lancedb_handler.LanceDBHandler", return_value=handler):
            ids = search_relevant_fact_ids(workspace_id="ws1", query="hello world")
        assert ids == ["f1", "f2"]

    def test_search_passes_limit_and_filter(self):
        handler = MagicMock()
        handler.search.return_value = [{"id": "f1"}]
        with patch("core.lancedb_handler.LanceDBHandler", return_value=handler):
            search_relevant_fact_ids(workspace_id="ws1", query="hello world", limit=3)
        _, kwargs = handler.search.call_args
        assert kwargs["table_name"] == "turn_facts"
        assert kwargs["query"] == "hello world"
        assert kwargs["limit"] == 3
        assert kwargs["filter_str"] == "workspace_id == 'ws1'"

    def test_search_escapes_quote_in_workspace(self):
        handler = MagicMock()
        handler.search.return_value = [{"id": "f1"}]
        with patch("core.lancedb_handler.LanceDBHandler", return_value=handler):
            search_relevant_fact_ids(workspace_id="ws'1", query="hello world")
        _, kwargs = handler.search.call_args
        assert kwargs["filter_str"] == "workspace_id == 'ws''1'"

    def test_search_empty_workspace_uses_no_filter(self):
        handler = MagicMock()
        handler.search.return_value = [{"id": "f1"}]
        with patch("core.lancedb_handler.LanceDBHandler", return_value=handler):
            search_relevant_fact_ids(workspace_id="", query="hello world")
            search_relevant_fact_ids(workspace_id=None, query="hello world")
        assert handler.search.call_count == 2
        for call in handler.search.call_args_list:
            assert call.kwargs["filter_str"] is None

    def test_search_exception_returns_empty(self):
        handler = MagicMock()
        handler.search.side_effect = RuntimeError("lancedb corrupt")
        with patch("core.lancedb_handler.LanceDBHandler", return_value=handler):
            assert search_relevant_fact_ids(workspace_id="ws1", query="hello world") == []

    def test_non_dict_result_without_id_skipped(self):
        handler = MagicMock()
        handler.search.return_value = ["plain-string"]
        with patch("core.lancedb_handler.LanceDBHandler", return_value=handler):
            assert search_relevant_fact_ids(workspace_id="ws1", query="hello world") == []


# ============================================================================
# middleware.governance_middleware — P3 gatekeeper config
# ============================================================================

class TestMaskResponseFields:
    def test_empty_masked_fields_returns_input_unchanged(self):
        from middleware.governance_middleware import mask_response_fields
        payload = {"access_token": "leak"}
        assert mask_response_fields(payload, set()) is payload

    def test_dict_values_masked_case_insensitively(self):
        from middleware.governance_middleware import mask_response_fields
        resp = {
            "ACCESS_TOKEN": "leak-1",
            "AccessToken": "leak-2",
            "data": {"accessToken": "leak-3"},
            "public": "ok",
        }
        masked = mask_response_fields(resp, masked_fields={"access_token"})
        assert masked["ACCESS_TOKEN"] == "***"
        assert masked["AccessToken"] == "***"
        assert masked["data"]["accessToken"] == "***"
        assert masked["public"] == "ok"

    def test_separator_variants_match(self):
        from middleware.governance_middleware import mask_response_fields
        masked = mask_response_fields(
            {"access-token": "1", "refresh_token": "2"},
            masked_fields={"access_token", "refresh-token"},
        )
        assert masked == {"access-token": "***", "refresh_token": "***"}

    def test_list_of_dicts_masked(self):
        from middleware.governance_middleware import mask_response_fields
        resp = [{"webhook_url": "x"}, "plain", {"nested": [{"bot_access_token": "y"}]}]
        masked = mask_response_fields(resp, masked_fields={"webhook_url", "bot_access_token"})
        assert masked[0]["webhook_url"] == "***"
        assert masked[1] == "plain"
        assert masked[2]["nested"][0]["bot_access_token"] == "***"

    def test_scalar_passthrough(self):
        from middleware.governance_middleware import mask_response_fields
        assert mask_response_fields("just a string", {"access_token"}) == "just a string"
        assert mask_response_fields(42, {"access_token"}) == 42


class TestGatekeeperConfig:
    def _gk(self):
        from middleware.governance_middleware import Gatekeeper
        return Gatekeeper()

    def test_normalize_service(self):
        gk = self._gk()
        assert gk._normalize_service("  Slack  ") == "slack"
        assert gk._normalize_service(None) == ""

    def test_configure_normalizes_and_get_matches(self):
        gk = self._gk()
        gk.configure("Slack ", {"masked_fields": {"access_token"}})
        assert gk._get("slack", "masked_fields", set()) == {"access_token"}
        assert gk._get("SLACK", "masked_fields", set()) == {"access_token"}

    def test_get_case_fallback_for_pre_normalization_keys(self):
        gk = self._gk()
        gk.configure("Slack", {"masked_fields": {"token"}})
        assert gk._get("SLACK", "masked_fields", set()) == {"token"}

    def test_get_case_fallback_for_hand_written_keys(self):
        gk = self._gk()
        gk._config = {"Slack": {"masked_fields": {"token"}}}
        assert gk._get("slack", "masked_fields", set()) == {"token"}

    def test_get_unconfigured_service_returns_plain_default(self):
        gk = self._gk()
        assert gk._get("unknown_svc", "some_key", "fallback") == "fallback"

    def test_get_mutations_default(self):
        gk = self._gk()
        assert gk._get("github", "mutations", None) == {"create_issue", "merge_pr", "delete_branch"}
        assert gk._get("nosuch", "mutations", None) == set()

    def test_get_masked_fields_default(self):
        gk = self._gk()
        assert gk._get("slack", "masked_fields", None) == {
            "access_token", "bot_access_token", "webhook_url",
        }
        assert gk._get("nosuch", "masked_fields", None) == set()

    def test_get_require_approval_default(self):
        gk = self._gk()
        assert gk._get("slack", "require_approval_for", None) == set()

    def test_get_configured_key_wins_over_default(self):
        gk = self._gk()
        gk.configure("slack", {"mutations": {"custom"}})
        assert gk._get("slack", "mutations", None) == {"custom"}

    def test_mask_response_uses_default_masked_fields(self):
        from middleware.governance_middleware import Gatekeeper
        gk = Gatekeeper()
        out = gk.mask_response("slack", {"access_token": "leak", "ok": True})
        assert out["access_token"] == "***"
        assert out["ok"] is True

    def test_mask_response_uses_configured_fields(self):
        gk = self._gk()
        gk.configure("custom_svc", {"masked_fields": {"api_key"}})
        out = gk.mask_response("custom_svc", {"api_key": "leak", "id": 1})
        assert out["api_key"] == "***"
        assert out["id"] == 1


class TestCheckActionRisk:
    async def _call(self, gk=None, **kwargs):
        from middleware.governance_middleware import Gatekeeper
        gk = gk or Gatekeeper()
        return await gk.check_action_risk(**kwargs)

    async def test_unconfigured_service_allows_and_audits(self):
        from middleware.governance_middleware import Gatekeeper
        gk = Gatekeeper()
        calls = []
        gk._write_audit = lambda **kw: calls.append(kw)
        with patch(
            "middleware.governance_middleware.rate_limiter.is_rate_limited",
            new=AsyncMock(return_value=(False, 10)),
        ):
            result = await gk.check_action_risk(
                "plain_svc", action="read", params={},
                agent_id="a1", workspace_id="ws1", user_id="u1", tenant_id="t1",
            )
        assert result == {"allowed": True}
        assert calls and calls[-1]["allowed"] is True
        assert calls[-1]["service"] == "plain_svc"
        assert calls[-1]["agent_id"] == "a1"

    async def test_rate_limited_blocks(self):
        from middleware.governance_middleware import Gatekeeper
        gk = Gatekeeper()
        with patch(
            "middleware.governance_middleware.rate_limiter.is_rate_limited",
            new=AsyncMock(return_value=(True, 0)),
        ):
            result = await gk.check_action_risk("svc", action="read")
        assert result["allowed"] is False
        assert "rate" in result["reason"].lower()

    async def test_configured_rate_limit_zero_blocks_without_limiter(self):
        from middleware.governance_middleware import Gatekeeper
        gk = Gatekeeper()
        gk.configure("svc_block", {"rate_limit": 0})
        with patch(
            "middleware.governance_middleware.rate_limiter.is_rate_limited",
            new=AsyncMock(return_value=(False, 999)),
        ) as lim:
            result = await gk.check_action_risk("svc_block", action="read")
        lim.assert_not_called()
        assert result["allowed"] is False
        assert "rate" in result["reason"].lower()

    async def test_configured_rate_limit_positive_uses_limiter(self):
        from middleware.governance_middleware import Gatekeeper
        gk = Gatekeeper()
        gk.configure("svc_limited", {"rate_limit": 5})
        with patch(
            "middleware.governance_middleware.rate_limiter.is_rate_limited",
            new=AsyncMock(return_value=(False, 3)),
        ) as lim:
            result = await gk.check_action_risk("svc_limited", action="read")
        lim.assert_awaited_once_with(connector_id="svc_limited", limit=5)
        assert result["allowed"] is True

    async def test_rate_limiter_exception_is_skipped(self):
        from middleware.governance_middleware import Gatekeeper
        gk = Gatekeeper()
        with patch(
            "middleware.governance_middleware.rate_limiter.is_rate_limited",
            new=AsyncMock(side_effect=RuntimeError("redis down")),
        ):
            result = await gk.check_action_risk("svc", action="read")
        assert result["allowed"] is True

    async def test_missing_required_scope_blocks(self):
        from middleware.governance_middleware import Gatekeeper
        gk = Gatekeeper()
        gk.configure("scoped", {"required_scopes": ["billing.write"]})
        with patch(
            "middleware.governance_middleware.rate_limiter.is_rate_limited",
            new=AsyncMock(return_value=(False, 10)),
        ):
            result = await gk.check_action_risk(
                "scoped", action="create", scopes={"billing.read"})
        assert result["allowed"] is False
        assert "scope" in result["reason"].lower()
        assert "billing.write" in result["reason"]

    async def test_required_scopes_present_allows(self):
        from middleware.governance_middleware import Gatekeeper
        gk = Gatekeeper()
        gk.configure("scoped", {"required_scopes": ["billing.write", "billing.read"]})
        with patch(
            "middleware.governance_middleware.rate_limiter.is_rate_limited",
            new=AsyncMock(return_value=(False, 10)),
        ):
            result = await gk.check_action_risk(
                "scoped", action="create", scopes={"billing.write", "billing.read", "extra"})
        assert result["allowed"] is True

    async def test_required_scopes_str_coercion(self):
        from middleware.governance_middleware import Gatekeeper
        gk = Gatekeeper()
        gk.configure("scoped", {"required_scopes": ["billing.write"]})
        with patch(
            "middleware.governance_middleware.rate_limiter.is_rate_limited",
            new=AsyncMock(return_value=(False, 10)),
        ):
            result = await gk.check_action_risk(
                "scoped", action="create", scopes={123, "billing.write"})
        assert result["allowed"] is True

    async def test_taint_allowed_continues(self):
        from middleware.governance_middleware import Gatekeeper
        gk = Gatekeeper()
        tracker = MagicMock()
        tracker.check_outbound.return_value = {"allowed": True}
        with patch(
            "middleware.governance_middleware.rate_limiter.is_rate_limited",
            new=AsyncMock(return_value=(False, 10)),
        ):
            result = await gk.check_action_risk("svc", action="send", taint_tracker=tracker)
        tracker.check_outbound.assert_called_once_with(destination="external", service="svc")
        assert result["allowed"] is True

    async def test_taint_blocked_fails_closed_with_violation(self):
        from middleware.governance_middleware import Gatekeeper
        gk = Gatekeeper()
        tracker = MagicMock()
        tracker.check_outbound.return_value = {
            "allowed": False,
            "reason": "restricted data observed",
            "violation_type": "VT_PROVENANCE",
            "max_observed": "restricted",
        }
        audits = []
        gk._write_audit = lambda **kw: audits.append(kw)
        with patch(
            "middleware.governance_middleware.rate_limiter.is_rate_limited",
            new=AsyncMock(return_value=(False, 10)),
        ):
            result = await gk.check_action_risk(
                "svc", action="send", taint_tracker=tracker, agent_id="a1",
                workspace_id="ws1",
            )
        assert result == {
            "allowed": False,
            "reason": "restricted data observed",
            "violation_type": "VT_PROVENANCE",
            "max_observed": "restricted",
        }
        assert audits and audits[0]["allowed"] is False

    async def test_taint_exception_fails_closed(self):
        """A taint tracker that cannot answer means restricted data cannot be
        ruled out — the gate must BLOCK (fail-closed), matching the repo-wide
        posture (cf. _check_hitl_policy). Previously this failed OPEN."""
        from middleware.governance_middleware import Gatekeeper
        gk = Gatekeeper()
        tracker = MagicMock()
        tracker.check_outbound.side_effect = RuntimeError("taint db down")
        with patch(
            "middleware.governance_middleware.rate_limiter.is_rate_limited",
            new=AsyncMock(return_value=(False, 10)),
        ):
            result = await gk.check_action_risk("svc", action="send", taint_tracker=tracker)
        assert result["allowed"] is False
        assert "unavailable" in result["reason"].lower()

    async def test_hitl_required_and_approved_pauses(self):
        from middleware.governance_middleware import Gatekeeper
        gk = Gatekeeper()
        gk.configure("stripe", {"require_approval_for": ["refund"]})
        with patch(
            "middleware.governance_middleware.intervention_service.request_intervention",
            new=AsyncMock(return_value={"action_id": "hitl-1"}),
        ) as req:
            result = await gk.check_action_risk(
                "stripe", action="refund", params={"amount": 10},
                agent_id="a1", workspace_id="ws1", user_id="u1",
            )
        req.assert_awaited_once()
        assert result["allowed"] is False
        assert result["intervention_id"] == "hitl-1"
        assert result["paused"] is True
        assert "review" in result["reason"]

    async def test_hitl_empty_response_fails_closed(self):
        from middleware.governance_middleware import Gatekeeper
        gk = Gatekeeper()
        gk.configure("stripe", {"require_approval_for": ["refund"]})
        with patch(
            "middleware.governance_middleware.intervention_service.request_intervention",
            new=AsyncMock(return_value={}),
        ):
            result = await gk.check_action_risk("stripe", action="refund")
        assert result["allowed"] is False
        assert "unavailable" in result["reason"].lower()

    async def test_hitl_exception_fails_closed(self):
        from middleware.governance_middleware import Gatekeeper
        gk = Gatekeeper()
        gk.configure("stripe", {"require_approval_for": ["refund"]})
        with patch(
            "middleware.governance_middleware.intervention_service.request_intervention",
            new=AsyncMock(side_effect=RuntimeError("hitl down")),
        ):
            result = await gk.check_action_risk("stripe", action="refund")
        assert result["allowed"] is False
        assert result.get("intervention_id") is None
        assert "unavailable" in result["reason"].lower()

    async def test_non_approved_action_not_paused(self):
        from middleware.governance_middleware import Gatekeeper
        gk = Gatekeeper()
        gk.configure("stripe", {"require_approval_for": ["refund"]})
        with patch(
            "middleware.governance_middleware.intervention_service.request_intervention",
            new=AsyncMock(),
        ) as req:
            result = await gk.check_action_risk("stripe", action="create_charge")
        req.assert_not_called()
        assert result["allowed"] is True

    async def test_blocked_mutation_audited_but_not_paused(self):
        from middleware.governance_middleware import Gatekeeper
        gk = Gatekeeper()
        gk.configure("svc", {"require_approval_for": ["delete"]})
        audits = []
        gk._write_audit = lambda **kw: audits.append(kw)
        with patch(
            "middleware.governance_middleware.intervention_service.request_intervention",
            new=AsyncMock(return_value={"action_id": "hitl-9"}),
        ):
            await gk.check_action_risk("svc", action="delete")
        assert len(audits) == 1
        assert audits[0]["allowed"] is False
        assert audits[0]["action"] == "delete"


# ============================================================================
# core.error_handlers
# ============================================================================

class TestErrorCodeEnum:
    def test_authentication_codes(self):
        assert ErrorCode.AUTHENTICATION_REQUIRED.value == "AUTH_REQUIRED"
        assert ErrorCode.INVALID_CREDENTIALS.value == "INVALID_CREDENTIALS"
        assert ErrorCode.TOKEN_EXPIRED.value == "TOKEN_EXPIRED"
        assert ErrorCode.PERMISSION_DENIED.value == "PERMISSION_DENIED"

    def test_validation_and_resource_codes(self):
        assert ErrorCode.VALIDATION_ERROR.value == "VALIDATION_ERROR"
        assert ErrorCode.MISSING_REQUIRED_FIELD.value == "MISSING_FIELD"
        assert ErrorCode.INVALID_VALUE.value == "INVALID_VALUE"
        assert ErrorCode.RESOURCE_NOT_FOUND.value == "NOT_FOUND"
        assert ErrorCode.RESOURCE_ALREADY_EXISTS.value == "ALREADY_EXISTS"
        assert ErrorCode.RESOURCE_CONFLICT.value == "CONFLICT"

    def test_business_and_system_codes(self):
        assert ErrorCode.BUSINESS_RULE_VIOLATION.value == "BUSINESS_RULE_VIOLATION"
        assert ErrorCode.OPERATION_NOT_ALLOWED.value == "OPERATION_NOT_ALLOWED"
        assert ErrorCode.EXTERNAL_SERVICE_ERROR.value == "EXTERNAL_SERVICE_ERROR"
        assert ErrorCode.INTERNAL_SERVER_ERROR.value == "INTERNAL_ERROR"
        assert ErrorCode.DATABASE_ERROR.value == "DATABASE_ERROR"
        assert ErrorCode.CONFIGURATION_ERROR.value == "CONFIGURATION_ERROR"

    def test_domain_specific_codes(self):
        assert ErrorCode.INVOICE_NOT_FOUND.value == "INVOICE_NOT_FOUND"
        assert ErrorCode.OAUTH_TOKEN_EXPIRED.value == "OAUTH_TOKEN_EXPIRED"
        assert ErrorCode.AGENT_GOVERNANCE_BLOCKED.value == "AGENT_GOVERNANCE_BLOCKED"
        assert ErrorCode.ENTITY_NOT_FOUND.value == "ENTITY_NOT_FOUND"

    def test_all_members_have_string_values(self):
        for member in ErrorCode:
            assert isinstance(member.value, str)
            assert member.value


class TestErrorModels:
    def test_error_response_defaults(self):
        resp = ErrorResponse(error_code="X", message="m", timestamp="t")
        assert resp.success is False
        assert resp.details is None
        assert resp.request_id is None

    def test_error_response_full(self):
        resp = ErrorResponse(
            error_code="X", message="m", details={"k": 1},
            timestamp="t", request_id="r1",
        )
        assert resp.dict(exclude_none=True)["details"] == {"k": 1}
        assert resp.request_id == "r1"

    def test_validation_error_detail(self):
        detail = ValidationErrorDetail(field="f", message="m", value=42)
        assert detail.field == "f"
        assert detail.message == "m"
        assert detail.value == 42

    def test_validation_error_detail_value_optional(self):
        detail = ValidationErrorDetail(field="f", message="m")
        assert detail.value is None


class TestApiError:
    def test_default_status_code_500(self):
        err = api_error(ErrorCode.INTERNAL_SERVER_ERROR, "boom")
        assert err.status_code == 500
        assert err.detail["success"] is False
        assert err.detail["error_code"] == "INTERNAL_ERROR"
        assert err.detail["message"] == "boom"
        assert err.detail["details"] == {}
        assert "timestamp" in err.detail

    def test_custom_status_and_details(self):
        err = api_error(
            ErrorCode.RESOURCE_NOT_FOUND, "Agent not found",
            details={"agent_id": "abc"}, status_code=404,
        )
        assert err.status_code == 404
        assert err.detail["error_code"] == "NOT_FOUND"
        assert err.detail["details"] == {"agent_id": "abc"}

    def test_request_id_included_when_provided(self):
        err = api_error(ErrorCode.VALIDATION_ERROR, "bad", request_id="rid-1")
        assert err.detail["request_id"] == "rid-1"

    def test_request_id_omitted_when_none(self):
        err = api_error(ErrorCode.VALIDATION_ERROR, "bad")
        assert "request_id" not in err.detail


class TestSuccessResponse:
    def test_with_data_and_message(self):
        resp = success_response({"agent_id": "a1"}, "Created")
        assert resp["success"] is True
        assert resp["data"] == {"agent_id": "a1"}
        assert resp["message"] == "Created"
        assert "timestamp" in resp

    def test_with_list_and_no_message(self):
        resp = success_response(["a", "b"])
        assert resp["data"] == ["a", "b"]
        assert resp["message"] is None


class TestPaginatedResponse:
    def test_single_page_no_next_prev(self):
        resp = paginated_response(["a"], total=1, page=1, page_size=50)
        assert resp["pagination"]["total_pages"] == 1
        assert resp["pagination"]["has_next"] is False
        assert resp["pagination"]["has_prev"] is False

    def test_middle_page_has_both(self):
        resp = paginated_response([], total=30, page=2, page_size=10)
        assert resp["pagination"]["total_pages"] == 3
        assert resp["pagination"]["has_next"] is True
        assert resp["pagination"]["has_prev"] is True

    def test_exact_multiple(self):
        resp = paginated_response([], total=20, page=2, page_size=10)
        assert resp["pagination"]["total_pages"] == 2
        assert resp["pagination"]["has_next"] is False

    def test_zero_page_size(self):
        resp = paginated_response([], total=10, page=2, page_size=0)
        assert resp["pagination"]["total_pages"] == 0
        assert resp["pagination"]["has_next"] is False
        assert resp["pagination"]["has_prev"] is True

    def test_first_page_has_no_prev(self):
        resp = paginated_response([], total=10, page=1, page_size=5)
        assert resp["pagination"]["has_prev"] is False
        assert resp["pagination"]["has_next"] is True


class TestGlobalExceptionHandler:
    @pytest.mark.asyncio
    async def test_generic_exception_production_message(self, monkeypatch):
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        resp = await global_exception_handler(make_request("rid-1"), RuntimeError("boom"))
        assert resp.status_code == 500
        body = resp.body.decode()
        assert "An internal server error occurred" in body
        assert "boom" not in body
        assert "INTERNAL_ERROR" in body
        assert "rid-1" in body
        assert '"details": null' in body or "details" not in body

    @pytest.mark.asyncio
    async def test_generic_exception_development_details(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        resp = await global_exception_handler(make_request(), ValueError("bad input"))
        assert resp.status_code == 500
        body = resp.body.decode()
        assert "ValueError: bad input" in body
        assert "traceback" in body

    @pytest.mark.asyncio
    async def test_atom_exception_delegates_to_atom_handler(self):
        from core.exceptions import AtomException, ErrorSeverity
        exc = AtomException(
            "agent gone", error_code=__import__("core.exceptions", fromlist=["ErrorCode"]).ErrorCode.AGENT_NOT_FOUND,  # noqa: E501
            severity=ErrorSeverity.MEDIUM,
        )
        resp = await global_exception_handler(make_request(), exc)
        assert resp.status_code == 400
        assert "AGENT_2001" in resp.body.decode()

    @pytest.mark.asyncio
    async def test_no_request_id_omitted(self, monkeypatch):
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        resp = await global_exception_handler(make_request(), RuntimeError("boom"))
        assert '"request_id": null' not in resp.body.decode()


class TestAtomExceptionHandler:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "severity_name,expected_status",
        [("CRITICAL", 500), ("HIGH", 500), ("MEDIUM", 400), ("LOW", 400), ("INFO", 200)],
    )
    async def test_severity_to_status_mapping(self, severity_name, expected_status):
        from core.exceptions import AtomException, ErrorSeverity, ErrorCode as CoreErrorCode
        exc = AtomException(
            "something happened",
            error_code=CoreErrorCode.VALIDATION_ERROR,
            severity=getattr(ErrorSeverity, severity_name),
            details={"field": "x"},
        )
        resp = await atom_exception_handler(make_request("rid"), exc)
        assert resp.status_code == expected_status
        assert "VAL_7001" in resp.body.decode()
        assert '"details":{"field":"x"}' in resp.body.decode()

    @pytest.mark.asyncio
    async def test_unknown_severity_defaults_to_500(self):
        fake = SimpleNamespace(
            severity=SimpleNamespace(value="bogus"),
            error_code=SimpleNamespace(value="WEIRD"),
            message="weird message",
            details=None,
            cause=None,
        )
        resp = await atom_exception_handler(make_request(), fake)
        assert resp.status_code == 500
        assert "WEIRD" in resp.body.decode()

    @pytest.mark.asyncio
    async def test_details_none_omitted(self):
        from core.exceptions import AtomException, ErrorSeverity
        from core.exceptions import ErrorCode as CoreErrorCode
        exc = AtomException(
            "no details", error_code=CoreErrorCode.INTERNAL_SERVER_ERROR,
            severity=ErrorSeverity.HIGH,
        )
        resp = await atom_exception_handler(make_request(), exc)
        body = resp.body.decode()
        assert '"details"' not in body

    @pytest.mark.asyncio
    async def test_cause_sets_exc_info(self):
        from core.exceptions import AtomException, ErrorSeverity
        from core.exceptions import ErrorCode as CoreErrorCode
        exc = AtomException(
            "with cause", error_code=CoreErrorCode.DATABASE_ERROR,
            severity=ErrorSeverity.CRITICAL, cause=RuntimeError("db"),
        )
        resp = await atom_exception_handler(make_request("r1"), exc)
        assert resp.status_code == 500
        assert "r1" in resp.body.decode()


class TestValidationErrorHandler:
    def test_creates_validation_exception(self):
        err = handle_validation_error("agent_name", "required", value="")
        assert err.status_code == 400
        assert err.detail["error_code"] == "VALIDATION_ERROR"
        assert err.detail["details"]["field"] == "agent_name"
        assert err.detail["details"]["message"] == "required"
        assert err.detail["details"]["value"] == ""

    def test_custom_status_code(self):
        err = handle_validation_error("f", "m", status_code=422)
        assert err.status_code == 422


class TestNotFoundHandler:
    def test_default_details_include_identity(self):
        err = handle_not_found("Agent", "agent-123")
        assert err.status_code == 404
        assert err.detail["error_code"] == "NOT_FOUND"
        assert err.detail["message"] == "Agent with ID 'agent-123' not found"
        assert err.detail["details"] == {
            "resource_type": "Agent", "resource_id": "agent-123",
        }

    def test_custom_details_passed_verbatim(self):
        # Contract (w116): caller details are PRESERVED and the resource
        # identity is merged in (setdefault) rather than discarded.
        err = handle_not_found(
            "Workspace", "w1", details={"workspace_name": "Test"},
        )
        assert err.detail["details"] == {
            "workspace_name": "Test",
            "resource_type": "Workspace",
            "resource_id": "w1",
        }


class TestPermissionDeniedHandler:
    def test_default_details(self):
        err = handle_permission_denied("delete", "Agent")
        assert err.status_code == 403
        assert err.detail["error_code"] == "PERMISSION_DENIED"
        assert err.detail["details"] == {"action": "delete", "resource_type": "Agent"}

    def test_custom_details(self):
        err = handle_permission_denied("delete", "Agent", details={"owner": "someone"})
        assert err.detail["details"] == {
            "owner": "someone",
            "action": "delete",
            "resource_type": "Agent",
        }


class TestInvoiceErrors:
    def test_base_error_defaults(self):
        err = InvoiceError("bad invoice", ErrorCode.INVOICE_VALIDATION_ERROR)
        assert err.message == "bad invoice"
        assert err.code == ErrorCode.INVOICE_VALIDATION_ERROR
        assert err.details == {}
        assert err.http_status == 500
        assert err.timestamp.tzinfo is not None

    def test_base_error_unmapped_code_defaults_500(self):
        err = InvoiceError("x", ErrorCode.AGENT_NOT_FOUND)
        assert err.http_status == 500

    def test_base_error_mapped_code(self):
        err = InvoiceError("x", ErrorCode.INVOICE_NOT_FOUND)
        assert err.http_status == 404

    def test_to_http_exception(self):
        err = InvoiceError("missing", ErrorCode.INVOICE_NOT_FOUND, {"id": 1})
        http = err.to_http_exception()
        assert http.status_code == 404
        assert http.detail["message"] == "missing"
        assert http.detail["details"] == {"id": 1}

    def test_not_found_default_invoice_type(self):
        err = InvoiceNotFoundError("Invoice 5 missing")
        assert err.code == ErrorCode.INVOICE_NOT_FOUND
        assert err.details["invoice_type"] == "unknown"

    def test_not_found_custom_invoice_type(self):
        err = InvoiceNotFoundError("missing", invoice_type="quote")
        assert err.details["invoice_type"] == "quote"

    def test_not_found_merges_custom_details(self):
        err = InvoiceNotFoundError("missing", details={"tenant": "t"})
        assert err.details == {"tenant": "t", "invoice_type": "unknown"}

    def test_validation_error(self):
        err = InvoiceValidationError("bad fields", {"field": "amount"})
        assert err.code == ErrorCode.INVOICE_VALIDATION_ERROR
        assert err.details == {"field": "amount"}

    def test_pricing_error(self):
        err = InvoicePricingError("cannot price")
        assert err.code == ErrorCode.INVOICE_PRICING_ERROR

    def test_http_status_map_values(self):
        assert HTTP_STATUS_MAP[ErrorCode.INVOICE_NOT_FOUND] == 404
        assert HTTP_STATUS_MAP[ErrorCode.INVOICE_VALIDATION_ERROR] == 500
        assert HTTP_STATUS_MAP[ErrorCode.APPOINTMENT_NOT_FOUND] == 404
        assert HTTP_STATUS_MAP[ErrorCode.ORDER_NOT_FOUND] == 404
        assert HTTP_STATUS_MAP[ErrorCode.OAUTH_TOKEN_INVALID] == 401
        assert HTTP_STATUS_MAP[ErrorCode.OAUTH_TOKEN_EXPIRED] == 401


class TestResultPattern:
    def test_ok(self):
        result = Result.ok(42)
        assert result.is_ok is True
        assert result.value == 42
        assert result.error is None

    def test_error_default_code(self):
        result = Result.error("failed")
        assert result.is_ok is False
        assert isinstance(result.error, InvoiceError)
        assert result.error.code == ErrorCode.INTERNAL_SERVER_ERROR

    def test_error_custom_code_and_details(self):
        result = Result.error("nope", ErrorCode.VALIDATION_ERROR, {"f": "x"})
        assert result.error.code == ErrorCode.VALIDATION_ERROR
        assert result.error.details == {"f": "x"}

    def test_from_invoice_exception(self):
        original = InvoiceError("orig", ErrorCode.INVOICE_NOT_FOUND)
        result = Result.from_exception(original)
        assert result.error is original

    def test_from_generic_exception(self):
        result = Result.from_exception(ValueError("bad"))
        assert result.error.code == ErrorCode.INTERNAL_SERVER_ERROR
        assert result.error.details == {"original_exception": "ValueError"}

    def test_unwrap_success(self):
        assert Result.ok("v").unwrap() == "v"

    def test_unwrap_raises_error(self):
        original = InvoiceError("nope", ErrorCode.INVOICE_NOT_FOUND)
        with pytest.raises(InvoiceError) as excinfo:
            Result.error("nope", ErrorCode.INVOICE_NOT_FOUND).unwrap()
        assert excinfo.value.message == "nope"

    def test_unwrap_unknown_error_raises(self):
        with pytest.raises(InvoiceError) as excinfo:
            Result(is_ok=False).unwrap()
        assert excinfo.value.message == "Unknown error"

    def test_unwrap_or_success(self):
        assert Result.ok("v").unwrap_or("d") == "v"

    def test_unwrap_or_failure(self):
        assert Result.error("nope").unwrap_or("d") == "d"

    def test_map_success(self):
        assert Result.ok(2).map(lambda x: x * 2).value == 4

    def test_map_raises_becomes_error(self):
        result = Result.ok(1).map(lambda x: 1 / 0)
        assert result.is_ok is False
        assert result.error.details["original_exception"] == "ZeroDivisionError"

    def test_map_on_error_returns_self(self):
        result = Result.error("nope")
        assert result.map(lambda x: x + 1) is result

    def test_and_then_chains(self):
        result = Result.ok(2).and_then(lambda x: Result.ok(x + 3))
        assert result.is_ok is True
        assert result.value == 5

    def test_and_then_stops_on_error(self):
        result = Result.error("nope").and_then(lambda x: Result.ok(1))
        assert result.is_ok is False


class TestAtomExceptionsAvailability:
    # Reload probes run in a subprocess: a reload of core.error_handlers in
    # this process would replace the module's class objects (ErrorCode,
    # InvoiceError, Result, ...), breaking class identity for every other
    # suite that imported them at collection time.
    def _run_subprocess_probe(self, body):
        # The child `python -c` process has no cwd on sys.path unless pytest
        # itself was started from backend/ — pass the backend root explicitly
        # so the probe works from any invocation directory.
        backend_root = str(pathlib.Path(__file__).resolve().parents[1])
        env = {**os.environ, "PYTHONPATH": backend_root + os.pathsep + os.environ.get("PYTHONPATH", "")}
        proc = subprocess.run(
            [sys.executable, "-c", body],
            capture_output=True, text=True, timeout=120, env=env,
        )
        assert proc.returncode == 0, proc.stderr + proc.stdout
        return proc.stdout

    def test_import_error_fallback_sets_flag_false(self):
        script = """
import importlib
from unittest.mock import patch
import core.error_handlers as eh
with patch.dict(__import__("sys").modules, {"core.exceptions": None}):
    importlib.reload(eh)
    assert eh.ATOM_EXCEPTIONS_AVAILABLE is False, "flag should be False"
importlib.reload(eh)
assert eh.ATOM_EXCEPTIONS_AVAILABLE is True, "restore should succeed"
print("OK")
"""
        out = self._run_subprocess_probe(script)
        assert "OK" in out

    @pytest.mark.asyncio
    async def test_atom_handler_falls_back_to_global_when_unavailable(self):
        script = """
import asyncio
import importlib
from types import SimpleNamespace
from unittest.mock import patch
import core.error_handlers as eh

async def main():
    fake = SimpleNamespace(
        severity=SimpleNamespace(value="medium"),
        error_code=SimpleNamespace(value="X"),
        message="m",
        details=None,
        cause=None,
    )
    request = SimpleNamespace(
        state=SimpleNamespace(request_id="r1"), url="http://t/")
    with patch.dict(__import__("sys").modules, {"core.exceptions": None}):
        importlib.reload(eh)
        resp = await eh.atom_exception_handler(request, fake)
        assert resp.status_code == 500, resp.body
        assert "INTERNAL_ERROR" in resp.body.decode()
    importlib.reload(eh)
    assert eh.ATOM_EXCEPTIONS_AVAILABLE is True
    print("OK")

asyncio.run(main())
"""
        out = self._run_subprocess_probe(script)
        assert "OK" in out
