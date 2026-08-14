"""Coverage wave 82c — core misc modules (standalone >=95% each).

Targets (all mocked, zero LLM spend, no network, no real DB):
  core/automation_settings.py
  core/backfill_job_queue.py
  core/base_routes.py
  core/budget_enforcement_service.py
  core/burnout_detection_engine.py
  core/constitutional_validator.py
  core/embedding_service.py
  core/hallucination_config.py
"""
from __future__ import annotations

import asyncio
import importlib
import json
import os
import sys
import types
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import HTTPException

from core.automation_settings import AutomationSettingsManager
from core.burnout_detection_engine import BurnoutDetectionEngine
from core.constitutional_validator import ConstitutionalValidator
from core.embedding_service import (
    EmbeddingService,
    generate_embedding,
    generate_embeddings_batch,
)

# ===========================================================================
# core/automation_settings.py
# ===========================================================================


class TestAutomationSettings:
    def _manager(self, tmp_path, exists: bool = True, content: str | None = None):
        path = tmp_path / "settings.json"
        if exists and content is not None:
            path.write_text(content)
        m = AutomationSettingsManager()
        m.SETTINGS_FILE = str(path)
        m._settings = m._load_settings()
        return m

    def test_default_settings_written_when_file_missing(self, tmp_path):
        m = self._manager(tmp_path, exists=False)
        data = json.loads((tmp_path / "settings.json").read_text())
        assert data == AutomationSettingsManager.DEFAULT_SETTINGS
        assert m.get_settings() == AutomationSettingsManager.DEFAULT_SETTINGS

    def test_load_settings_merges_file_over_defaults(self, tmp_path):
        m = self._manager(tmp_path, content=json.dumps({"response_control_mode": "auto_send"}))
        assert m._settings["response_control_mode"] == "auto_send"
        assert m._settings["enable_sales_automations"] is True

    def test_load_settings_error_falls_back_to_defaults(self, tmp_path):
        m = AutomationSettingsManager()
        m.SETTINGS_FILE = str(tmp_path / "settings.json")
        with patch("builtins.open", side_effect=OSError("boom")):
            m._settings = m._load_settings()
        assert m._settings == AutomationSettingsManager.DEFAULT_SETTINGS.copy()

    def test_load_settings_corrupt_json_falls_back_to_defaults(self, tmp_path):
        m = self._manager(tmp_path, content="{not valid json")
        assert m._settings == AutomationSettingsManager.DEFAULT_SETTINGS.copy()

    def test_save_settings_error_is_logged(self, tmp_path):
        m = self._manager(tmp_path, exists=False)
        with patch("builtins.open", side_effect=OSError("boom")):
            m.update_settings({"x": 1})  # must not raise

    def test_get_settings_returns_copy(self, tmp_path):
        m = self._manager(tmp_path, exists=False)
        s = m.get_settings()
        s["enable_sales_automations"] = False
        assert m.get_settings()["enable_sales_automations"] is True

    def test_update_settings_persists_and_returns_internal(self, tmp_path):
        m = self._manager(tmp_path, exists=False)
        result = m.update_settings({"enable_accounting_automations": False, "pipelines": {"sales": {"mode": "manual"}}})
        assert result is m._settings
        assert json.loads((tmp_path / "settings.json").read_text())["enable_accounting_automations"] is False

    @pytest.mark.parametrize("key,method", [
        ("enable_automatic_knowledge_extraction", "is_extraction_enabled"),
        ("enable_out_of_workflow_automations", "is_automations_enabled"),
        ("enable_accounting_automations", "is_accounting_enabled"),
        ("enable_sales_automations", "is_sales_enabled"),
    ])
    def test_toggle_helpers(self, tmp_path, key, method):
        m = self._manager(tmp_path, exists=False)
        assert getattr(m, method)() is True
        m._settings[key] = False
        assert getattr(m, method)() is False

    def test_toggle_helpers_default_true_when_key_missing(self, tmp_path):
        m = self._manager(tmp_path, exists=False)
        m._settings = {}
        assert m.is_extraction_enabled() is True
        assert m.is_automations_enabled() is True
        assert m.is_accounting_enabled() is True
        assert m.is_sales_enabled() is True

    def test_module_singleton_and_getter(self):
        from core.automation_settings import automation_settings_manager, get_automation_settings
        assert get_automation_settings() is automation_settings_manager


# ===========================================================================
# core/backfill_job_queue.py
# ===========================================================================


class TestBackfillJobQueue:
    @pytest.fixture
    def queue(self):
        from core.backfill_job_queue import BackfillJobQueue
        return BackfillJobQueue(redis_url="redis://mock:6379/0", max_retries=4)

    @pytest.fixture
    def client(self):
        c = AsyncMock()
        return c

    def _wire(self, queue, client):
        queue.get_client = AsyncMock(return_value=client)

    async def test_get_client_creates_pool_once(self):
        from core.backfill_job_queue import BackfillJobQueue
        q = BackfillJobQueue(redis_url="redis://x:1/0")
        with patch("core.backfill_job_queue.ConnectionPool.from_url") as m_from, \
                patch("core.backfill_job_queue.redis.Redis") as m_redis:
            m_from.return_value = MagicMock()
            client = MagicMock()
            m_redis.return_value = client
            c1 = await q.get_client()
            assert c1 is client
            assert q._pool is m_from.return_value
            c2 = await q.get_client()
            assert c2 is client
            m_from.assert_called_once()

    async def test_close_with_client_and_pool(self):
        from core.backfill_job_queue import BackfillJobQueue
        q = BackfillJobQueue()
        q._client = AsyncMock()
        q._pool = AsyncMock()
        await q.close()
        q._client.close.assert_awaited_once()
        q._pool.disconnect.assert_awaited_once()

    async def test_close_without_client_or_pool(self):
        from core.backfill_job_queue import BackfillJobQueue
        q = BackfillJobQueue()
        q._client = None
        q._pool = None
        await q.close()

    async def test_schedule_entity_type_backfill(self, queue, client):
        self._wire(queue, client)
        job_id = await queue.schedule_entity_type_backfill(
            tenant_id="t1", slug="customer", display_name="Customer",
            json_schema={"type": "object"}, source="salesforce", ttl_hours=72,
        )
        assert job_id.startswith("entity_type:t1:customer:")
        client.hset.assert_awaited_once()
        client.set.assert_awaited()
        client.rpush.assert_awaited_once_with("job:queue:t1", job_id)
        stored = client.hset.call_args.kwargs["mapping"]
        assert json.loads(stored["json_schema"]) == {"type": "object"}
        assert stored["ttl_hours"] == 72

    async def test_schedule_node_migration(self, queue, client):
        self._wire(queue, client)
        job_id = await queue.schedule_node_migration("t1", "w1", "customer", batch_size=500)
        assert job_id.startswith("node_migration:t1:w1:customer:")
        stored = client.hset.call_args.kwargs["mapping"]
        assert stored["batch_size"] == 500
        assert stored["job_type"] == "node_migration"

    async def test_schedule_ttl_cleanup(self, queue, client):
        self._wire(queue, client)
        job_id = await queue.schedule_ttl_cleanup("t1", interval_hours=6)
        assert job_id.startswith("ttl_cleanup:t1:")
        stored = client.hset.call_args.kwargs["mapping"]
        assert stored["interval_hours"] == 6
        assert stored["job_type"] == "ttl_cleanup"

    async def test_schedule_job_sets_all_keys(self, queue, client):
        self._wire(queue, client)
        await queue._schedule_job("j1", {"job_type": "x", "tenant_id": "t1"}, "t1")
        client.hset.assert_awaited_once_with("job:data:j1", mapping={"job_type": "x", "tenant_id": "t1"})
        calls = [c.args[0] for c in client.set.await_args_list]
        assert "job:status:j1" in calls and "job:retry:j1" in calls
        client.rpush.assert_awaited_once_with("job:queue:t1", "j1")

    async def test_get_job_status_full_decode(self, queue, client):
        self._wire(queue, client)
        client.get.side_effect = [b"processing", b"3"]
        client.hgetall.side_effect = [
            {b"job_type": b"entity_type_backfill", b"ttl_hours": b"48",
             b"json_schema": b'{"type":"object"}', b"slug": b"customer"},
            {b"message": b"working"},
        ]
        status = await queue.get_job_status("j1")
        assert status["status"] == "processing"
        assert status["job_type"] == "entity_type_backfill"
        assert status["ttl_hours"] == 48
        assert status["json_schema"] == {"type": "object"}
        assert status["retry_count"] == 3
        assert status["progress"] == {"message": "working"}

    async def test_get_job_status_string_keys_and_corrupt_json(self, queue, client):
        self._wire(queue, client)
        client.get.side_effect = [None, None]
        client.hgetall.side_effect = [
            {"job_type": "ttl_cleanup", "interval_hours": "2", "available_skills": "{bad json", "plain": "v"},
            {},
        ]
        status = await queue.get_job_status("j1")
        assert status["status"] == "unknown"
        assert status["interval_hours"] == 2
        assert status["available_skills"] == "{bad json"
        assert status["plain"] == "v"
        assert status["retry_count"] == 0

    def test_parse_retry_count(self):
        from core.backfill_job_queue import BackfillJobQueue
        assert BackfillJobQueue._parse_retry_count(None) == 0
        assert BackfillJobQueue._parse_retry_count(b"") == 0
        assert BackfillJobQueue._parse_retry_count(b"7") == 7
        assert BackfillJobQueue._parse_retry_count(b"abc") == 0
        assert BackfillJobQueue._parse_retry_count("12") == 12

    async def test_update_job_progress_with_message(self, queue, client):
        self._wire(queue, client)
        await queue.update_job_progress("j1", 42.5, "halfway")
        mapping = client.hset.call_args.kwargs["mapping"]
        assert mapping["progress"] == "42.5"
        assert mapping["message"] == "halfway"

    async def test_update_job_progress_no_message(self, queue, client):
        self._wire(queue, client)
        await queue.update_job_progress("j1", 10)
        assert client.hset.call_args.kwargs["mapping"]["message"] == ""

    async def test_set_job_status(self, queue, client):
        self._wire(queue, client)
        from core.backfill_job_queue import BackfillJobStatus
        await queue.set_job_status("j1", BackfillJobStatus.COMPLETED)
        client.set.assert_awaited_once_with("job:status:j1", "completed")

    async def test_process_job_success(self, queue, client):
        self._wire(queue, client)
        client.get.return_value = b"0"
        queue._execute_job = AsyncMock()
        await queue.process_job_with_retry("j1")
        assert client.set.await_args_list[0].args[1] == "processing"
        assert client.set.await_args_list[1].args[1] == "completed"

    async def test_process_job_retry_schedules(self, queue, client):
        self._wire(queue, client)
        client.get.return_value = b"0"
        queue._execute_job = AsyncMock(side_effect=ValueError("boom"))
        await queue.process_job_with_retry("j1")
        client.incr.assert_awaited_once_with("job:retry:j1")
        client.expire.assert_awaited_once_with("job:data:j1", 60)
        statuses = [c.args[1] for c in client.set.await_args_list]
        assert "retrying" in statuses

    async def test_process_job_retry_delay_clamped_to_last(self, queue, client):
        queue.retry_delays = [5]
        queue.max_retries = 10
        self._wire(queue, client)
        client.get.return_value = b"9"
        queue._execute_job = AsyncMock(side_effect=ValueError("boom"))
        await queue.process_job_with_retry("j1")
        client.expire.assert_awaited_once_with("job:data:j1", 5)

    async def test_process_job_dead_letter_after_max(self, queue, client):
        self._wire(queue, client)
        client.get.return_value = b"4"
        queue._execute_job = AsyncMock(side_effect=ValueError("boom"))
        await queue.process_job_with_retry("j1")
        client.incr.assert_not_awaited()
        assert "dead_letter" in [c.args[1] for c in client.set.await_args_list]

    async def test_process_job_retry_count_none(self, queue, client):
        self._wire(queue, client)
        client.get.return_value = None
        queue._execute_job = AsyncMock(side_effect=ValueError("boom"))
        await queue.process_job_with_retry("j1")
        client.incr.assert_awaited()

    async def test_execute_entity_type_valid(self, queue, client):
        self._wire(queue, client)
        client.hgetall.return_value = {
            b"job_type": b"entity_type_backfill", b"json_schema": b'{"type": "object"}'
        }
        await queue._execute_job("j1")

    async def test_execute_entity_type_schema_missing_field(self, queue, client):
        self._wire(queue, client)
        client.hgetall.return_value = {
            b"job_type": b"entity_type_backfill", b"json_schema": b'{}'
        }
        with pytest.raises(ValueError, match="type.*or.*\$schema"):
            await queue._execute_job("j1")

    async def test_execute_entity_type_schema_not_dict(self, queue, client):
        self._wire(queue, client)
        client.hgetall.return_value = {
            b"job_type": b"entity_type_backfill", b"json_schema": b'[1, 2]'
        }
        with pytest.raises(ValueError, match="dictionary"):
            await queue._execute_job("j1")

    async def test_execute_entity_type_schema_invalid_json(self, queue, client):
        self._wire(queue, client)
        client.hgetall.return_value = {
            b"job_type": b"entity_type_backfill", b"json_schema": b'{broken'
        }
        with pytest.raises(ValueError, match="Invalid JSON schema"):
            await queue._execute_job("j1")

    async def test_execute_node_migration_valid(self, queue, client):
        self._wire(queue, client)
        client.hgetall.return_value = {b"job_type": b"node_migration", b"batch_size": b"500"}
        await queue._execute_job("j1")

    async def test_execute_node_migration_invalid_batch(self, queue, client):
        self._wire(queue, client)
        for bad in (b"0", b"20000"):
            client.hgetall.return_value = {b"job_type": b"node_migration", b"batch_size": bad}
            with pytest.raises(ValueError, match="batch_size"):
                await queue._execute_job("j1")

    async def test_execute_node_migration_non_numeric(self, queue, client):
        self._wire(queue, client)
        client.hgetall.return_value = {b"job_type": b"node_migration", b"batch_size": b"abc"}
        with pytest.raises(ValueError):
            await queue._execute_job("j1")

    async def test_execute_ttl_cleanup_passes(self, queue, client):
        self._wire(queue, client)
        client.hgetall.return_value = {b"job_type": b"ttl_cleanup"}
        await queue._execute_job("j1")

    async def test_execute_unknown_job_type_warns(self, queue, client):
        self._wire(queue, client)
        client.hgetall.return_value = {b"job_type": b"mystery"}
        await queue._execute_job("j1")

    async def test_execute_job_type_str_key(self, queue, client):
        self._wire(queue, client)
        client.hgetall.return_value = {"job_type": "entity_type_backfill", "json_schema": b'{"type":"object"}'}
        await queue._execute_job("j1")

    async def test_get_next_job(self, queue, client):
        self._wire(queue, client)
        client.blpop.return_value = (b"job:queue:t1", b"job-123")
        assert await queue.get_next_job("t1") == "job-123"
        client.blpop.assert_awaited_once_with("job:queue:t1", timeout=5)

    async def test_get_next_job_empty(self, queue, client):
        self._wire(queue, client)
        client.blpop.return_value = None
        assert await queue.get_next_job("t1") is None

    async def test_get_queue_size(self, queue, client):
        self._wire(queue, client)
        client.llen.return_value = 3
        assert await queue.get_queue_size("t1") == 3
        client.llen.assert_awaited_once_with("job:queue:t1")

    async def test_clear_queue(self, queue, client):
        self._wire(queue, client)
        await queue.clear_queue("t1")
        client.delete.assert_awaited_once_with("job:queue:t1")

    def test_enums(self):
        from core.backfill_job_queue import BackfillJobStatus, BackfillJobType
        assert BackfillJobType("entity_type_backfill").value == "entity_type_backfill"
        assert BackfillJobStatus("processing").value == "processing"
        assert len(list(BackfillJobType)) == 4
        assert len(list(BackfillJobStatus)) == 6

    def test_retry_delays_default(self):
        from core.backfill_job_queue import BackfillJobQueue
        assert BackfillJobQueue().retry_delays == [60, 300, 900, 3600]
        assert BackfillJobQueue(retry_delays=[1, 2]).retry_delays == [1, 2]

    def test_get_backfill_job_queue_singleton(self):
        import core.backfill_job_queue as mod
        old = mod._job_queue
        mod._job_queue = None
        try:
            with patch.dict(os.environ, {"REDIS_URL": "redis://singleton:1/0"}):
                q1 = mod.get_backfill_job_queue()
                assert q1.redis_url == "redis://singleton:1/0"
                assert mod.get_backfill_job_queue() is q1
        finally:
            mod._job_queue = old


# ===========================================================================
# core/base_routes.py
# ===========================================================================


class TestBaseAPIRouter:
    @pytest.fixture
    def router(self):
        from core.base_routes import BaseAPIRouter
        return BaseAPIRouter()

    def test_success_response_minimal(self, router):
        resp = router.success_response(data={"a": 1})
        assert resp["success"] is True and resp["data"] == {"a": 1}
        assert "message" not in resp and "metadata" not in resp

    def test_success_response_full(self, router):
        resp = router.success_response(data=[1], message="done", metadata={"page": 1}, status_code=201)
        assert resp["message"] == "done" and resp["metadata"] == {"page": 1}

    def test_success_list_response_full(self, router):
        resp = router.success_list_response(items=["a", "b"], total=10, page=1, page_size=2, message="hi")
        assert resp["data"] == ["a", "b"]
        assert resp["metadata"] == {"total": 10, "page": 1, "page_size": 2}
        assert resp["message"] == "hi"

    def test_success_list_response_partial(self, router):
        resp = router.success_list_response(items=["a"], total=1)
        assert resp["metadata"] == {"total": 1}
        assert resp["message"] == "Retrieved 1 items"

    def test_success_list_response_no_metadata(self, router):
        resp = router.success_list_response(items=[])
        assert "metadata" not in resp
        assert resp["message"] == "Retrieved 0 items"

    def test_error_response_minimal(self, router):
        exc = router.error_response("X", "boom")
        assert exc.status_code == 400
        body = exc.detail
        assert body["success"] is False
        assert body["error"]["code"] == "X" and body["error"]["message"] == "boom"

    def test_error_response_with_details(self, router):
        exc = router.error_response("X", "boom", details={"k": "v"}, status_code=418)
        assert exc.status_code == 418
        assert exc.detail["error"]["details"] == {"k": "v"}

    def test_error_response_debug_mode_stack_trace(self, router):
        router._debug_mode = True
        exc = router.error_response("X", "boom")
        assert "stack_trace" in exc.detail["error"]

    def test_validation_error(self, router):
        exc = router.validation_error("email", "bad", details={"extra": 1})
        assert exc.status_code == 422
        assert exc.detail["error"]["details"] == {"field": "email", "extra": 1}

    def test_validation_error_no_details(self, router):
        exc = router.validation_error("email", "bad")
        assert exc.detail["error"]["details"] == {"field": "email"}

    def test_not_found_full(self, router):
        exc = router.not_found_error("Agent", "a1", details={"hint": "x"})
        assert exc.status_code == 404
        assert exc.detail["error"]["message"] == "Agent not found: a1"
        assert exc.detail["error"]["details"]["resource_id"] == "a1"

    def test_not_found_no_id(self, router):
        exc = router.not_found_error("Agent")
        assert exc.detail["error"]["message"] == "Agent not found"
        assert "resource_id" not in exc.detail["error"]["details"]

    def test_permission_denied_full(self, router):
        exc = router.permission_denied_error("delete", "Agent", {"required": "AUTONOMOUS"})
        assert exc.status_code == 403
        assert exc.detail["error"]["message"] == "Permission denied: delete on Agent"
        assert exc.detail["error"]["details"]["required"] == "AUTONOMOUS"

    def test_permission_denied_minimal(self, router):
        exc = router.permission_denied_error("delete")
        assert exc.detail["error"]["message"] == "Permission denied: delete"
        assert exc.detail["error"]["details"] == {"action": "delete"}

    def test_unauthorized(self, router):
        exc = router.unauthorized_error(details={"hint": "x"})
        assert exc.status_code == 401
        assert exc.detail["error"]["code"] == "UNAUTHORIZED"

    def test_unauthorized_default_message(self, router):
        exc = router.unauthorized_error()
        assert exc.detail["error"]["message"] == "Authentication required"

    def test_conflict_full(self, router):
        exc = router.conflict_error("exists", conflicting_resource="r1", details={"d": 1})
        assert exc.status_code == 409
        assert exc.detail["error"]["details"] == {"conflicting_resource": "r1", "d": 1}

    def test_conflict_minimal(self, router):
        exc = router.conflict_error("exists")
        assert "details" not in exc.detail["error"]

    def test_rate_limit_full(self, router):
        exc = router.rate_limit_error(retry_after=30, details={"d": 1})
        assert exc.status_code == 429
        assert exc.detail["error"]["details"] == {"retry_after": 30, "d": 1}

    def test_rate_limit_minimal(self, router):
        exc = router.rate_limit_error()
        assert "details" not in exc.detail["error"]

    def test_internal_error_default(self, router):
        exc = router.internal_error()
        assert exc.status_code == 500
        assert exc.detail["error"]["message"] == "An internal error occurred"

    def test_internal_error_str_detail_overwrites_default(self, router):
        exc = router.internal_error(detail="kaboom")
        assert exc.detail["error"]["message"] == "kaboom"

    def test_internal_error_str_detail_appends_to_custom(self, router):
        exc = router.internal_error(message="custom", detail="kaboom")
        assert exc.detail["error"]["message"] == "custom: kaboom"

    def test_internal_error_dict_detail(self, router):
        exc = router.internal_error(detail={"nested": 1})
        assert exc.detail["error"]["details"] == {"nested": 1}

    def test_internal_error_dict_detail_keeps_existing_details(self, router):
        exc = router.internal_error(details={"existing": 1}, detail={"nested": 1})
        assert exc.detail["error"]["details"] == {"existing": 1}

    def test_governance_denied_with_reason(self, router):
        exc = router.governance_denied_error("a1", "send_email", "STUDENT", "AUTONOMOUS", reason="too risky")
        assert exc.status_code == 403
        assert exc.detail["error"]["message"] == "Permission denied: send_email on Agent"
        assert exc.detail["error"]["details"]["agent_id"] == "a1"
        assert exc.detail["error"]["details"]["maturity_level"] == "STUDENT"
        assert exc.detail["error"]["details"]["required_maturity"] == "AUTONOMOUS"
        assert exc.detail["error"]["details"]["reason"] == "too risky"

    def test_governance_denied_no_reason(self, router):
        exc = router.governance_denied_error("a1", "send_email", "STUDENT", "AUTONOMOUS")
        assert exc.detail["error"]["details"]["reason"] == "Requires AUTONOMOUS maturity level"

    def test_log_api_call_full(self, router, caplog):
        with caplog.at_level("INFO"):
            router.log_api_call("/api/x", "POST", user_id="u1", extra_data={"extra": 1})
        assert any("API Call: POST /api/x" in r.message for r in caplog.records)

    def test_log_api_call_minimal(self, router, caplog):
        with caplog.at_level("INFO"):
            router.log_api_call("/api/x", "GET")
        assert any("API Call: GET /api/x" in r.message for r in caplog.records)

    def test_router_debug_mode_from_env(self):
        from core.base_routes import BaseAPIRouter
        with patch.dict(os.environ, {"DEBUG": "true"}):
            assert BaseAPIRouter()._debug_mode is True
        with patch.dict(os.environ, {"DEBUG": "false"}):
            assert BaseAPIRouter()._debug_mode is False

    @pytest.mark.asyncio
    async def test_atom_exception_handler_dict_detail(self):
        from core.base_routes import atom_exception_handler
        resp = await atom_exception_handler(Mock(), HTTPException(status_code=404, detail={"success": False}))
        assert resp.status_code == 404
        assert json.loads(resp.body) == {"success": False}

    @pytest.mark.asyncio
    async def test_atom_exception_handler_str_detail(self):
        from core.base_routes import atom_exception_handler
        resp = await atom_exception_handler(Mock(), HTTPException(status_code=404, detail="missing"))
        body = json.loads(resp.body)
        assert resp.status_code == 404
        assert body["success"] is False and body["error"]["code"] == "HTTP_ERROR"

    @pytest.mark.asyncio
    async def test_generic_exception_handler_prod(self):
        from core.base_routes import generic_exception_handler
        request = SimpleNamespace(url=SimpleNamespace(path="/api/x"), method="GET")
        with patch.dict(os.environ, {"DEBUG": "false"}):
            resp = await generic_exception_handler(request, ValueError("secret detail"))
        body = json.loads(resp.body)
        assert resp.status_code == 500
        assert body["error"]["message"] == "An internal error occurred"

    @pytest.mark.asyncio
    async def test_generic_exception_handler_debug(self):
        from core.base_routes import generic_exception_handler
        request = SimpleNamespace(url=SimpleNamespace(path="/api/x"), method="GET")
        with patch.dict(os.environ, {"DEBUG": "true"}):
            resp = await generic_exception_handler(request, ValueError("secret detail"))
        body = json.loads(resp.body)
        assert body["error"]["message"] == "secret detail"
        assert body["error"]["type"] == "ValueError"
        assert "stack_trace" in body["error"]


class TestSafeDbOperation:
    def test_wrapper_injects_db_when_expected(self):
        from core.base_routes import safe_db_operation

        def op(db, agent_id):
            return (db, agent_id)

        db_mock = Mock()
        cm = MagicMock()
        cm.__enter__.return_value = db_mock
        with patch("core.database.get_db_session", return_value=cm):
            result = safe_db_operation(op)(agent_id="agent-1")
        assert result[0] is db_mock
        assert result[1] == "agent-1"

    def test_wrapper_no_db_param(self):
        from core.base_routes import safe_db_operation

        def op(agent_id):
            return f"done:{agent_id}"

        db_mock = Mock()
        cm = MagicMock()
        cm.__enter__.return_value = db_mock
        with patch("core.database.get_db_session", return_value=cm):
            result = safe_db_operation(op)("agent-1")
        assert result == "done:agent-1"

    def test_wrapper_raises_http_exception_on_error(self):
        from core.base_routes import safe_db_operation

        def op(agent_id):
            raise RuntimeError("db down")

        cm = MagicMock()
        cm.__enter__.side_effect = RuntimeError("db down")
        with patch("core.database.get_db_session", return_value=cm):
            with pytest.raises(HTTPException) as ei:
                safe_db_operation(op, error_message="custom failure")("agent-1")
        assert ei.value.status_code == 500
        body = ei.value.detail
        assert body["error"]["code"] == "DATABASE_ERROR"
        assert body["error"]["message"] == "custom failure"


class TestExecuteDbQuery:
    def test_success(self):
        from core.base_routes import execute_db_query
        db_mock = Mock()
        cm = MagicMock()
        cm.__enter__.return_value = db_mock
        with patch("core.database.get_db_session", return_value=cm):
            result = execute_db_query(lambda db: db.query("x"))
        assert result is db_mock.query.return_value

    def test_error_returns_default(self):
        from core.base_routes import execute_db_query

        def fail(db):
            raise RuntimeError("boom")

        cm = MagicMock()
        cm.__enter__.side_effect = RuntimeError("boom")
        with patch("core.database.get_db_session", return_value=cm):
            assert execute_db_query(fail, return_value={"fallback": True}) == {"fallback": True}

    def test_error_raises_http_exception(self):
        from core.base_routes import execute_db_query

        def fail(db):
            raise RuntimeError("boom")

        cm = MagicMock()
        cm.__enter__.side_effect = RuntimeError("boom")
        with patch("core.database.get_db_session", return_value=cm):
            with pytest.raises(HTTPException) as ei:
                execute_db_query(fail, error_message="query failed")
        assert ei.value.status_code == 500
        assert ei.value.detail["error"]["message"] == "query failed"


# ===========================================================================
# core/budget_enforcement_service.py
# ===========================================================================


class TestBudgetEnforcement:
    @pytest.fixture
    def service(self):
        from core.budget_enforcement_service import BudgetEnforcementService
        db = Mock()
        svc = BudgetEnforcementService(db=db)
        svc.spend_service = Mock()
        svc.spend_service.update_tenant_spend = Mock(return_value={"error": "unconfigured"})
        svc.spend_service.get_fleet_spend = Mock(return_value=0.0)
        svc.notification_service = Mock()
        svc.notification_service.send_notification = AsyncMock(return_value={"ok": True})
        return svc

    @pytest.fixture
    def db(self, service):
        return service.db

    def _setting(self, value: str | None):
        return SimpleNamespace(setting_value=value)

    def _mode(self, mode: str):
        return self._setting(json.dumps({"enforcement": {"mode": mode}}))

    def _billing(self, extra: dict):
        d = {"enforcement": {"mode": "soft_stop"}}
        d["enforcement"].update(extra)
        return self._setting(json.dumps(d))

    # ---- check_budget_before_action ---------------------------------------

    async def test_check_spend_error_fails_open(self, service, db):
        service.spend_service.update_tenant_spend.return_value = {"error": "boom"}
        result = await service.check_budget_before_action("t1", "a1", "act")
        assert result["allowed"] is True
        assert result["reason"] == "Unable to verify spend"

    async def test_check_under_budget_allowed(self, service, db):
        service.spend_service.update_tenant_spend.return_value = {
            "current_spend_usd": 50.0, "budget_limit_usd": 100.0, "utilization_percent": 50.0
        }
        db.query.return_value.filter.return_value.first.return_value = None
        result = await service.check_budget_before_action("t1", "a1", "act")
        assert result["allowed"] is True
        assert result["current_spend_usd"] == 50.0

    async def test_check_under_budget_fleet_blocked(self, service, db):
        from core.models import DelegationChain
        service.spend_service.update_tenant_spend.return_value = {
            "current_spend_usd": 50.0, "budget_limit_usd": 100.0, "utilization_percent": 50.0
        }

        def query_side_effect(model):
            chain = Mock()
            if model is DelegationChain:
                chain.filter.return_value.first.return_value = SimpleNamespace(total_spend_usd=10.0)
            else:
                chain.filter.return_value.first.return_value = None
            return chain

        db.query.side_effect = query_side_effect
        service.spend_service.get_fleet_spend.return_value = 20.0
        result = await service.check_budget_before_action("t1", "a1", "act", chain_id="c1")
        assert result["allowed"] is False
        assert "Fleet aggregate budget" in result["reason"]
        assert result["utilization_percent"] == 200.0

    async def test_check_under_budget_fleet_zero_limit_allowed(self, service, db):
        from core.models import DelegationChain
        service.spend_service.update_tenant_spend.return_value = {
            "current_spend_usd": 50.0, "budget_limit_usd": 100.0, "utilization_percent": 50.0
        }

        def query_side_effect(model):
            chain = Mock()
            if model is DelegationChain:
                chain.filter.return_value.first.return_value = SimpleNamespace(total_spend_usd=0.0)
            else:
                chain.filter.return_value.first.return_value = None
            return chain

        db.query.side_effect = query_side_effect
        service.spend_service.get_fleet_spend.return_value = 5.0
        result = await service.check_budget_before_action("t1", "a1", "act", chain_id="c1")
        assert result["allowed"] is True

    async def test_check_under_budget_no_chain(self, service, db):
        service.spend_service.update_tenant_spend.return_value = {
            "current_spend_usd": 50.0, "budget_limit_usd": 100.0, "utilization_percent": 50.0
        }
        db.query.return_value.filter.return_value.first.return_value = None
        result = await service.check_budget_before_action("t1", "a1", "act", chain_id="missing")
        assert result["allowed"] is True

    async def test_check_alert_only_allows_when_exceeded(self, service, db):
        service.spend_service.update_tenant_spend.return_value = {
            "current_spend_usd": 150.0, "budget_limit_usd": 100.0, "utilization_percent": 100.0
        }
        db.query.return_value.filter.return_value.first.return_value = self._mode("alert_only")
        result = await service.check_budget_before_action("t1", "a1", "act")
        assert result["allowed"] is True
        assert result["enforcement_mode"] == "alert_only"

    async def test_check_soft_stop_active_episode_allowed(self, service, db):
        service.spend_service.update_tenant_spend.return_value = {
            "current_spend_usd": 150.0, "budget_limit_usd": 100.0, "utilization_percent": 100.0
        }
        db.query.return_value.filter.return_value.first.return_value = self._mode("soft_stop")
        db.query.return_value.filter.return_value.scalar.return_value = 1
        result = await service.check_budget_before_action("t1", "a1", "act")
        assert result["allowed"] is True
        assert result["reason"] == "Active episode allowed to complete"

    async def test_check_soft_stop_blocks_new_episodes(self, service, db):
        service.spend_service.update_tenant_spend.return_value = {
            "current_spend_usd": 150.0, "budget_limit_usd": 100.0, "utilization_percent": 100.0
        }
        db.query.return_value.filter.return_value.first.return_value = self._mode("soft_stop")
        db.query.return_value.filter.return_value.scalar.return_value = 0
        result = await service.check_budget_before_action("t1", "a1", "act")
        assert result["allowed"] is False
        assert "New episodes blocked" in result["reason"]

    async def test_check_hard_stop_blocks(self, service, db):
        service.spend_service.update_tenant_spend.return_value = {
            "current_spend_usd": 150.0, "budget_limit_usd": 100.0, "utilization_percent": 100.0
        }
        db.query.return_value.filter.return_value.first.return_value = self._mode("hard_stop")
        result = await service.check_budget_before_action("t1", "a1", "act")
        assert result["allowed"] is False

    async def test_check_approval_valid_override(self, service, db):
        service.spend_service.update_tenant_spend.return_value = {
            "current_spend_usd": 150.0, "budget_limit_usd": 100.0, "utilization_percent": 100.0
        }
        override = {"expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}
        db.query.return_value.filter.return_value.first.return_value = self._billing({"mode": "approval", "override": override})
        result = await service.check_budget_before_action("t1", "a1", "act")
        assert result["allowed"] is True
        assert result["reason"] == "Admin override approved"

    async def test_check_approval_no_override(self, service, db):
        service.spend_service.update_tenant_spend.return_value = {
            "current_spend_usd": 150.0, "budget_limit_usd": 100.0, "utilization_percent": 100.0
        }
        db.query.return_value.filter.return_value.first.return_value = self._mode("approval")
        result = await service.check_budget_before_action("t1", "a1", "act")
        assert result["allowed"] is False
        assert "Admin approval required" in result["reason"]

    async def test_check_unknown_mode_falls_open(self, service, db):
        service.spend_service.update_tenant_spend.return_value = {
            "current_spend_usd": 150.0, "budget_limit_usd": 100.0, "utilization_percent": 100.0
        }
        with patch.object(service, "_get_enforcement_mode", return_value="bogus_mode"):
            result = await service.check_budget_before_action("t1", "a1", "act")
        assert result["allowed"] is True

    async def test_check_exception_fails_open(self, service, db):
        service.spend_service.update_tenant_spend.side_effect = RuntimeError("boom")
        result = await service.check_budget_before_action("t1", "a1", "act")
        assert result["allowed"] is True
        assert result["reason"] == "Unable to verify spend"

    # ---- enforce_budget ----------------------------------------------------

    async def test_enforce_tenant_not_found(self, service, db):
        db.query.return_value.filter.return_value.first.return_value = None
        result = await service.enforce_budget("t1", 10, 5, 200)
        assert result["success"] is False
        assert "not found" in result["error"]

    async def test_enforce_hard_stop(self, service, db):
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id="t1")
        db.query.return_value.filter.return_value.all.return_value = [
            SimpleNamespace(id="e1", status="running"),
            SimpleNamespace(id="e2", status="running"),
        ]
        with patch.object(service, "_get_enforcement_mode", return_value="hard_stop"):
            result = await service.enforce_budget("t1", 10, 5, 200)
        assert result["success"] is True
        assert result["episodes_cancelled"] == 2
        assert result["notification_sent"] is True
        service.notification_service.send_notification.assert_awaited()

    async def test_enforce_soft_stop(self, service, db):
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id="t1")
        db.query.return_value.filter.return_value.all.return_value = []
        with patch.object(service, "_get_enforcement_mode", return_value="soft_stop"):
            result = await service.enforce_budget("t1", 10, 5, 200)
        assert result["success"] is True
        assert result["notification_sent"] is True
        assert "episodes_cancelled" not in result

    async def test_enforce_approval_valid_override(self, service, db):
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id="t1")
        override = {"expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}
        db.query.return_value.filter.return_value.first.return_value = self._billing({"mode": "approval", "override": override})
        with patch.object(service, "_get_enforcement_mode", return_value="approval"):
            result = await service.enforce_budget("t1", 10, 5, 200)
        assert result["success"] is True
        assert result["override_active"] is True
        service.notification_service.send_notification.assert_not_awaited()

    async def test_enforce_approval_requests_approval(self, service, db):
        from core.models import Tenant, TenantSetting

        def query_side_effect(model):
            chain = Mock()
            if model is Tenant:
                chain.filter.return_value.first.return_value = SimpleNamespace(id="t1")
            elif model is TenantSetting:
                chain.filter.return_value.first.return_value = self._mode("approval")
            else:
                chain.filter.return_value.all.return_value = [SimpleNamespace(id="u1")]
                chain.filter.return_value.limit.return_value.all.return_value = []
            return chain

        db.query.side_effect = query_side_effect
        with patch.object(service, "_get_enforcement_mode", return_value="approval"):
            result = await service.enforce_budget("t1", 10, 5, 200)
        assert result["success"] is True
        assert result["approval_required"] is True
        service.notification_service.send_notification.assert_awaited()

    async def test_enforce_alert_only(self, service, db):
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id="t1")
        with patch.object(service, "_get_enforcement_mode", return_value="alert_only"):
            result = await service.enforce_budget("t1", 10, 5, 200)
        assert result["success"] is True
        assert result["enforcement_action"] == "none"

    async def test_enforce_exception(self, service, db):
        db.query.side_effect = RuntimeError("boom")
        result = await service.enforce_budget("t1", 10, 5, 200)
        assert result["success"] is False
        assert "boom" in result["error"]

    # ---- _get_enforcement_mode ---------------------------------------------

    def test_mode_from_setting(self, service, db):
        db.query.return_value.filter.return_value.first.return_value = self._mode("hard_stop")
        assert service._get_enforcement_mode("t1") == "hard_stop"

    def test_mode_invalid_defaults_soft_stop(self, service, db):
        db.query.return_value.filter.return_value.first.return_value = self._mode("wat")
        assert service._get_enforcement_mode("t1") == "soft_stop"

    def test_mode_no_setting_defaults_soft_stop(self, service, db):
        db.query.return_value.filter.return_value.first.return_value = None
        assert service._get_enforcement_mode("t1") == "soft_stop"

    def test_mode_corrupt_json_defaults_soft_stop(self, service, db):
        db.query.return_value.filter.return_value.first.return_value = self._setting("{broken")
        assert service._get_enforcement_mode("t1") == "soft_stop"

    def test_mode_empty_value_defaults_soft_stop(self, service, db):
        db.query.return_value.filter.return_value.first.return_value = self._setting(None)
        assert service._get_enforcement_mode("t1") == "soft_stop"

    # ---- override helpers --------------------------------------------------

    def test_get_budget_override_found(self, service, db):
        db.query.return_value.filter.return_value.first.return_value = self._billing({"override": {"user_id": "u1"}})
        assert service._get_budget_override("t1") == {"user_id": "u1"}

    def test_get_budget_override_missing(self, service, db):
        db.query.return_value.filter.return_value.first.return_value = self._mode("soft_stop")
        assert service._get_budget_override("t1") is None

    def test_get_budget_override_corrupt(self, service, db):
        db.query.return_value.filter.return_value.first.return_value = self._setting("{broken")
        assert service._get_budget_override("t1") is None

    def test_override_valid(self, service, db):
        override = {"expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}
        assert service._is_override_valid(override) is True

    def test_override_none(self, service, db):
        assert service._is_override_valid(None) is False

    def test_override_missing_expiry(self, service, db):
        assert service._is_override_valid({"user_id": "u1"}) is False

    def test_override_expired(self, service, db):
        override = {"expires_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()}
        assert service._is_override_valid(override) is False

    def test_override_invalid_iso(self, service, db):
        assert service._is_override_valid({"expires_at": "not-a-date"}) is False

    def test_override_naive_expiry_type_error(self, service, db):
        assert service._is_override_valid({"expires_at": "2020-01-01T00:00:00"}) is False

    def test_set_override_tenant_not_found(self, service, db):
        db.query.return_value.filter.return_value.first.return_value = None
        result = service._set_budget_override("t1", "u1")
        assert result["success"] is False

    def test_set_override_existing_setting(self, service, db):
        existing = SimpleNamespace(tenant_id="t1", setting_key="billing", setting_value='{"enforcement": {}}')
        db.query.return_value.filter.return_value.first.side_effect = [SimpleNamespace(id="t1"), existing]
        result = service._set_budget_override("t1", "u1")
        assert result["success"] is True
        assert existing.setting_value != '{"enforcement": {}}'
        assert json.loads(existing.setting_value)["enforcement"]["override"]["user_id"] == "u1"
        db.flush.assert_called()

    def test_set_override_new_setting(self, service, db):
        db.query.return_value.filter.return_value.first.side_effect = [SimpleNamespace(id="t1"), None]
        with patch("core.budget_enforcement_service.TenantSetting") as m_cls:
            result = service._set_budget_override("t1", "u1")
        assert result["success"] is True
        m_cls.assert_called_once()
        db.add.assert_called_once()
        db.flush.assert_called()

    def test_set_override_corrupt_existing_setting(self, service, db):
        existing = SimpleNamespace(tenant_id="t1", setting_key="billing", setting_value="{broken")
        db.query.return_value.filter.return_value.first.side_effect = [SimpleNamespace(id="t1"), existing]
        result = service._set_budget_override("t1", "u1")
        assert result["success"] is True
        assert json.loads(existing.setting_value)["enforcement"]["override"]["user_id"] == "u1"

    def test_set_override_exception_rolls_back(self, service, db):
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id="t1")
        db.flush.side_effect = RuntimeError("flush failed")
        result = service._set_budget_override("t1", "u1")
        assert result["success"] is False
        db.rollback.assert_called()

    # ---- _has_active_episodes / _cancel_active_episodes --------------------

    def test_has_active_episodes_true(self, service, db):
        db.query.return_value.filter.return_value.scalar.return_value = 3
        assert service._has_active_episodes("t1", "a1") is True

    def test_has_active_episodes_false(self, service, db):
        db.query.return_value.filter.return_value.scalar.return_value = 0
        assert service._has_active_episodes("t1", "a1") is False

    def test_has_active_episodes_error(self, service, db):
        db.query.side_effect = RuntimeError("boom")
        assert service._has_active_episodes("t1", "a1") is False

    def test_cancel_active_episodes(self, service, db):
        episodes = [SimpleNamespace(id="e1", status="running"), SimpleNamespace(id="e2", status="running")]
        db.query.return_value.filter.return_value.all.return_value = episodes
        assert service._cancel_active_episodes("t1") == 2
        assert episodes[0].status == "cancelled" and episodes[1].status == "cancelled"
        db.flush.assert_called()

    def test_cancel_active_episodes_none(self, service, db):
        db.query.return_value.filter.return_value.all.return_value = []
        assert service._cancel_active_episodes("t1") == 0

    def test_cancel_active_episodes_error(self, service, db):
        db.query.side_effect = RuntimeError("boom")
        assert service._cancel_active_episodes("t1") == 0
        db.rollback.assert_called()

    # ---- _send_enforcement_notification ------------------------------------

    async def test_send_notification_to_admins(self, service, db):
        db.query.return_value.filter.return_value.all.return_value = [SimpleNamespace(id="u1")]
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id="w1")
        ok = await service._send_enforcement_notification("t1", "hard_stop", 10.0, 5.0, 200.0, "details here")
        assert ok is True
        args = service.notification_service.send_notification.await_args
        assert args.args[0] == "u1"
        assert args.args[1] == "budget_enforcement"
        data = args.args[2]
        assert "Hard Stop" in data["title"]
        assert data["metadata"]["enforcement_mode"] == "hard_stop"
        assert data["priority"] == "high"

    async def test_send_notification_fallback_to_any_user(self, service, db):
        db.query.return_value.filter.return_value.all.side_effect = RuntimeError("attribute error")
        db.query.return_value.filter.return_value.limit.return_value.all.return_value = [SimpleNamespace(id="u9")]
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id="w1")
        ok = await service._send_enforcement_notification("t1", "soft_stop", 1.0, 1.0, 100.0, "d")
        assert ok is True
        assert service.notification_service.send_notification.await_args.args[0] == "u9"

    async def test_send_notification_no_users(self, service, db):
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.limit.return_value.all.return_value = []
        ok = await service._send_enforcement_notification("t1", "soft_stop", 1.0, 1.0, 100.0, "d")
        assert ok is False

    async def test_send_notification_no_workspace(self, service, db):
        db.query.return_value.filter.return_value.all.return_value = [SimpleNamespace(id="u1")]
        db.query.return_value.filter.return_value.first.return_value = None
        ok = await service._send_enforcement_notification("t1", "soft_stop", 1.0, 1.0, 100.0, "d")
        assert ok is False

    async def test_send_notification_unknown_mode_label(self, service, db):
        db.query.return_value.filter.return_value.all.return_value = [SimpleNamespace(id="u1")]
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id="w1")
        ok = await service._send_enforcement_notification("t1", "mystery_mode", 1.0, 1.0, 100.0, "d")
        assert ok is True
        assert "mystery_mode" in service.notification_service.send_notification.await_args.args[2]["title"]

    async def test_send_notification_error(self, service, db):
        service.notification_service.send_notification.side_effect = RuntimeError("nope")
        db.query.return_value.filter.return_value.all.return_value = [SimpleNamespace(id="u1")]
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id="w1")
        ok = await service._send_enforcement_notification("t1", "soft_stop", 1.0, 1.0, 100.0, "d")
        assert ok is False

    # ---- clear_enforcement_state -------------------------------------------

    def test_clear_state_no_setting(self, service, db):
        db.query.return_value.filter.return_value.first.return_value = None
        service.clear_enforcement_state("t1")
        db.flush.assert_not_called()

    def test_clear_state_no_override(self, service, db):
        db.query.return_value.filter.return_value.first.return_value = self._mode("soft_stop")
        service.clear_enforcement_state("t1")
        db.flush.assert_not_called()

    def test_clear_state_removes_override(self, service, db):
        existing = self._setting(json.dumps({"enforcement": {"mode": "approval", "override": {"user_id": "u1"}}}))
        db.query.return_value.filter.return_value.first.return_value = existing
        service.clear_enforcement_state("t1")
        data = json.loads(existing.setting_value)
        assert "override" not in data["enforcement"]
        db.flush.assert_called()

    def test_clear_state_error(self, service, db):
        db.query.return_value.filter.return_value.first.side_effect = RuntimeError("boom")
        service.clear_enforcement_state("t1")
        db.rollback.assert_called()

    # ---- lifecycle ----------------------------------------------------------

    def test_context_manager_and_close(self, service, db):
        with service as svc:
            assert svc is service
        db.close.assert_called()
        service.close()
        assert db.close.call_count == 2


# ===========================================================================
# core/burnout_detection_engine.py
# ===========================================================================


class TestBurnoutDetectionEngine:
    @pytest.fixture
    def engine(self):
        from core.burnout_detection_engine import BurnoutDetectionEngine
        return BurnoutDetectionEngine()

    async def test_burnout_critical_all_high(self, engine):
        metrics = {
            "meeting_metrics": {"total_hours": 8, "day_count": 1},
            "task_metrics": {"open_tasks": 100, "previous_open_tasks": 10},
            "comm_metrics": {"avg_response_latency_hours": 10},
        }
        result = await engine.calculate_burnout_risk(**metrics)
        assert result.risk_level == "Critical"
        assert result.score == 100.0
        assert result.factors["meeting_density"] == 100.0
        assert result.type == "burnout"
        assert any("Focus Time" in r for r in result.recommendations)
        assert any("delegating" in r for r in result.recommendations)
        assert any("Do Not Disturb" in r for r in result.recommendations)

    async def test_burnout_high_level(self, engine):
        result = await engine.calculate_burnout_risk(
            meeting_metrics={"total_hours": 5, "day_count": 1},
            task_metrics={"open_tasks": 12, "previous_open_tasks": 10},
            comm_metrics={},
        )
        assert result.risk_level == "High"
        assert 60 <= result.score < 80

    async def test_burnout_medium_level(self, engine):
        result = await engine.calculate_burnout_risk(
            meeting_metrics={"total_hours": 3, "day_count": 1},
            task_metrics={"open_tasks": 10, "previous_open_tasks": 10},
            comm_metrics={},
        )
        assert result.risk_level == "Medium"
        assert 40 <= result.score < 60

    async def test_burnout_low_level(self, engine):
        result = await engine.calculate_burnout_risk(
            meeting_metrics={}, task_metrics={}, comm_metrics={}
        )
        assert result.risk_level == "Low"
        assert result.score == 0.0
        assert result.recommendations == []

    async def test_burnout_zero_day_count_guard(self, engine):
        result = await engine.calculate_burnout_risk(
            meeting_metrics={"total_hours": 6, "day_count": 0},
            task_metrics={"open_tasks": 0, "previous_open_tasks": 0},
            comm_metrics={},
        )
        assert result.risk_level == "Medium"
        assert result.factors["backlog_growth"] == 0.0

    async def test_burnout_custom_settings(self):
        engine = BurnoutDetectionEngine(settings={
            "max_meeting_hours_daily": 2.0,
            "max_backlog_growth_rate": 2.0,
            "latency_threshold_hours": 8.0,
            "deadline_buffer_days": 1.0,
        })
        result = await engine.calculate_burnout_risk(
            meeting_metrics={"total_hours": 1.5, "day_count": 1},
            task_metrics={"open_tasks": 4, "previous_open_tasks": 2},
            comm_metrics={"avg_response_latency_hours": 5},
        )
        assert result.score == 78.75  # 75*0.4 + 100*0.3 + 62.5*0.3
        assert result.risk_level == "High"

    def test_singleton(self):
        from core.burnout_detection_engine import burnout_engine
        assert burnout_engine.settings["max_meeting_hours_daily"] == 5.0

    # ---- deadline risk ------------------------------------------------------

    def _task(self, title, due_iso, progress=0.0, est=10.0):
        return {"id": title, "title": title, "due_date": due_iso, "progress": progress, "estimated_hours": est}

    async def test_deadline_critical(self, engine):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        tasks = [self._task("A", future), self._task("B", future)]
        result = await engine.calculate_deadline_risk(tasks)
        assert result.risk_level == "Critical"
        assert result.score == 100.0
        assert result.factors["at_risk_count"] == 2
        assert result.type == "deadline"
        assert len(result.recommendations) == 3

    async def test_deadline_high(self, engine):
        future = (datetime.now(timezone.utc) + timedelta(hours=10)).isoformat()
        result = await engine.calculate_deadline_risk([self._task("A", future, progress=0.0, est=10.0)])
        assert result.risk_level == "High"
        assert result.factors["at_risk_count"] == 1
        assert "A" in result.recommendations[0]

    async def test_deadline_medium(self, engine):
        future = (datetime.now(timezone.utc) + timedelta(hours=10)).isoformat()
        result = await engine.calculate_deadline_risk([self._task("A", future, progress=0.4, est=10.0)])
        assert result.risk_level == "Medium"

    async def test_deadline_low(self, engine):
        future = (datetime.now(timezone.utc) + timedelta(hours=100)).isoformat()
        result = await engine.calculate_deadline_risk([self._task("A", future, progress=0.0, est=1.0)])
        assert result.risk_level == "Low"
        assert result.factors["at_risk_count"] == 0
        assert result.recommendations == []

    async def test_deadline_naive_datetime(self, engine):
        future = (datetime.now() + timedelta(hours=10)).isoformat()
        result = await engine.calculate_deadline_risk([self._task("A", future)])
        assert result.risk_level == "High"

    async def test_deadline_z_suffix_string(self, engine):
        future = (datetime.now(timezone.utc) + timedelta(hours=10)).isoformat().replace("+00:00", "Z")
        result = await engine.calculate_deadline_risk([self._task("A", future)])
        assert result.risk_level == "High"

    async def test_deadline_empty_tasks(self, engine):
        result = await engine.calculate_deadline_risk([])
        assert result.risk_level == "Low"
        assert result.score == 0.0
        assert result.factors == {"total_tasks": 0, "at_risk_count": 0}

    async def test_deadline_mixed_risk(self, engine):
        far = (datetime.now(timezone.utc) + timedelta(hours=100)).isoformat()
        near = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        result = await engine.calculate_deadline_risk([
            self._task("safe", far, progress=0.9, est=1.0),
            self._task("risky", near, progress=0.0, est=10.0),
        ])
        assert result.risk_level == "Critical"
        assert "risky" in result.recommendations[0]

    # ---- recommendations ----------------------------------------------------

    def test_recommendations_meeting_only(self, engine):
        recs = engine._generate_recommendations("High", {"meeting_density": 80, "backlog_growth": 0, "comm_latency": 0})
        assert len(recs) == 2

    def test_recommendations_backlog_only(self, engine):
        recs = engine._generate_recommendations("High", {"meeting_density": 0, "backlog_growth": 80, "comm_latency": 0})
        assert len(recs) == 2

    def test_recommendations_latency_only(self, engine):
        recs = engine._generate_recommendations("High", {"meeting_density": 0, "backlog_growth": 0, "comm_latency": 80})
        assert len(recs) == 2

    def test_recommendations_low_none(self, engine):
        assert engine._generate_recommendations("Low", {"meeting_density": 0, "backlog_growth": 0, "comm_latency": 0}) == []

    def test_recommendations_threshold_boundary(self, engine):
        assert engine._generate_recommendations("Medium", {"meeting_density": 70, "backlog_growth": 70, "comm_latency": 70}) == []


# ===========================================================================
# core/constitutional_validator.py
# ===========================================================================


class TestConstitutionalValidator:
    @pytest.fixture
    def validator(self):
        from core.constitutional_validator import ConstitutionalValidator
        return ConstitutionalValidator(db=Mock())

    def test_get_rules(self, validator):
        rules = validator.get_rules()
        assert "safety_no_harm" in rules
        assert rules["safety_no_harm"]["category"] == "safety"

    def test_validate_none_actions(self, validator):
        result = validator.validate_actions(None)
        assert result["compliant"] is True
        assert result["total_actions"] == 0
        assert result["score"] == 1.0

    def test_validate_skips_none_entries(self, validator):
        result = validator.validate_actions([None, {"type": "read", "content": "hello"}])
        assert result["total_actions"] == 2
        assert result["compliant"] is True

    def test_validate_clean_actions(self, validator):
        actions = [{"type": "read", "content": "fetch the sales report"}, {"type": "write", "content": "update doc"}]
        result = validator.validate_actions(actions)
        assert result["compliant"] is True
        assert result["violations"] == []
        assert result["score"] == 1.0

    def test_pii_ssn_detected(self, validator):
        result = validator.validate_actions([{"type": "log", "content": "user SSN is 123-45-6789"}])
        assert result["compliant"] is True  # HIGH severity only, not CRITICAL
        assert result["violations"][0]["rule_id"] == "safety_no_pii_exposure"
        assert "SSN" in result["violations"][0]["details"]

    def test_pii_credit_card_detected(self, validator):
        result = validator.validate_actions([{"type": "log", "content": "card 4111111111111111 ok"}])
        assert result["violations"][0]["rule_id"] == "safety_no_pii_exposure"
        assert "Credit Card" in result["violations"][0]["details"]

    def test_pii_email_detected(self, validator):
        result = validator.validate_actions([{"type": "log", "content": "mail user@example.com now"}])
        assert result["violations"][0]["rule_id"] == "safety_no_pii_exposure"
        assert "Email" in result["violations"][0]["details"]

    def test_pii_not_detected_clean(self, validator):
        result = validator.validate_actions([{"type": "log", "content": "plain text here"}])
        assert result["violations"] == []

    def test_financial_payment_unapproved(self, validator):
        result = validator.validate_actions([{"type": "make_payment", "content": "pay invoice 42"}])
        assert result["violations"][0]["rule_id"] == "financial_no_unauthorized_payments"
        assert result["violations"][0]["severity"] == "critical"
        assert result["compliant"] is False

    def test_financial_transfer_unapproved(self, validator):
        result = validator.validate_actions([{"type": "transfer", "content": "move funds"}])
        assert result["violations"][0]["rule_id"] == "financial_no_unauthorized_payments"

    def test_financial_payout_approved_via_metadata(self, validator):
        result = validator.validate_actions([{"type": "payout", "content": "x", "metadata": {"is_approved": True}}])
        assert result["violations"] == []

    def test_financial_approved_via_action_flag(self, validator):
        result = validator.validate_actions([{"type": "payment", "content": "x", "is_approved": True,
                                              "metadata": {"audit_log_id": "a1"}}])
        assert result["violations"] == []

    def test_audit_trail_sensitive_missing_id(self, validator):
        result = validator.validate_actions([{"type": "delete", "content": "drop row"}])
        assert result["violations"][0]["rule_id"] == "governance_audit_trail"
        assert "audit_log_id" in result["violations"][0]["details"]

    def test_audit_trail_with_audit_id(self, validator):
        result = validator.validate_actions([{"type": "delete", "content": "x", "metadata": {"audit_log_id": "a1"}}])
        assert result["violations"] == []

    def test_domain_filter_skips_nonmatching(self, validator):
        actions = [{"type": "payment", "content": "x", "metadata": {"is_approved": True, "audit_log_id": "a1"}}]
        result = validator.validate_actions(actions, domain="sales")
        assert result["violations"] == []

    def test_domain_matching_applies(self, validator):
        actions = [{"type": "payment", "content": "pay 100"}]
        result = validator.validate_actions(actions, domain="financial")
        assert any(v["rule_id"] == "financial_no_unauthorized_payments" for v in result["violations"])

    def test_action_type_fallback_key(self, validator):
        result = validator.validate_actions([{"action_type": "payment", "content": "x"}])
        assert any(v["rule_id"] == "financial_no_unauthorized_payments" for v in result["violations"])

    def test_action_type_default_unknown(self, validator):
        result = validator.validate_actions([{"content": "x", "metadata": {"is_approved": True}}])
        assert result["violations"] == []

    def test_compliance_score_mixed_severities(self, validator):
        violations = [
            {"severity": "critical"},
            {"severity": "high"},
            {"severity": "medium"},
            {"severity": "low"},
        ]
        score = validator._calculate_compliance_score(violations, 4)
        expected = max(0.0, 1.0 - (10 + 5 + 2 + 0.5) / 40.0)
        assert score == pytest.approx(expected)

    def test_compliance_score_unknown_severity_default_weight(self, validator):
        score = validator._calculate_compliance_score([{"severity": "weird"}], 1)
        assert score == pytest.approx(1.0 - 1.0 / 10.0)

    def test_compliance_score_missing_severity(self, validator):
        score = validator._calculate_compliance_score([{}], 1)
        assert score == pytest.approx(1.0 - 0.5 / 10.0)

    def test_compliance_score_zero_actions(self, validator):
        assert validator._calculate_compliance_score([], 0) == 1.0

    def test_compliance_score_no_violations(self, validator):
        assert validator._calculate_compliance_score([], 3) == 1.0

    def test_compliance_score_zero_after_heavy_penalty(self, validator):
        score = validator._calculate_compliance_score([{"severity": "critical"}, {"severity": "critical"}], 1)
        assert score == 0.0

    def test_calculate_score_public(self, validator):
        score = validator.calculate_score([{"severity": "high"}])
        assert score == pytest.approx(1.0 - 5.0 / 10.0)

    def test_calculate_score_empty(self, validator):
        assert validator.calculate_score([]) == 1.0

    def test_check_compliance_adds_domain(self, validator):
        result = validator.check_compliance("financial", [{"type": "read", "content": "x"}])
        assert result["domain"] == "financial"
        assert result["compliant"] is True

    def test_factory(self):
        from core.constitutional_validator import get_constitutional_validator
        v = get_constitutional_validator(db=Mock())
        assert isinstance(v, ConstitutionalValidator)


# ===========================================================================
# core/embedding_service.py
# ===========================================================================


class TestEmbeddingServiceInit:
    def test_default_provider_fastembed(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("core.embedding_service.LLMService"):
                svc = EmbeddingService()
        assert svc.provider == "fastembed"

    def test_provider_from_env(self):
        with patch.dict(os.environ, {"EMBEDDING_PROVIDER": "openai"}):
            with patch("core.embedding_service.LLMService"):
                svc = EmbeddingService()
        assert svc.provider == "openai"
        assert svc.model == "text-embedding-3-small"

    def test_local_alias_normalized(self):
        with patch("core.embedding_service.LLMService"):
            svc = EmbeddingService(provider="local")
        assert svc.provider == "fastembed"

    def test_unknown_provider_raises(self):
        with patch("core.embedding_service.LLMService"):
            with pytest.raises(ValueError, match="Unknown embedding provider"):
                EmbeddingService(provider="bogus")

    def test_custom_config_model_and_ids(self):
        with patch("core.embedding_service.LLMService") as m_llm:
            svc = EmbeddingService(provider="openai", model="my-model", config={"k": "v"},
                                   workspace_id="w1", tenant_id="t1")
        assert svc.model == "my-model"
        assert svc.config == {"k": "v"}
        assert svc.workspace_id == "w1" and svc.tenant_id == "t1"
        m_llm.assert_called_once_with(workspace_id="w1", tenant_id="t1")

    def test_default_ids(self):
        with patch("core.embedding_service.LLMService"):
            svc = EmbeddingService(provider="fastembed")
        assert svc.workspace_id == "default" and svc.tenant_id == "default"

    def test_get_default_model_variants(self):
        with patch.dict(os.environ, {"FASTEMBED_MODEL": "custom-fast", "OPENAI_EMBEDDING_MODEL": "custom-openai"}):
            with patch("core.embedding_service.LLMService"):
                svc = EmbeddingService(provider="fastembed")
                assert svc._get_default_model() == "custom-fast"
                svc2 = EmbeddingService(provider="openai")
                assert svc2._get_default_model() == "custom-openai"
                svc3 = EmbeddingService(provider="cohere")
                assert svc3._get_default_model() == "embed-english-v3.0"
        with patch("core.embedding_service.LLMService"):
            svc4 = EmbeddingService(provider="fastembed")
            assert svc4._get_default_model() == "BAAI/bge-small-en-v1.5"
            svc4.provider = "unknown"
            assert svc4._get_default_model() == "BAAI/bge-small-en-v1.5"


class TestEmbeddingGeneration:
    @pytest.fixture
    def fast_service(self):
        with patch("core.embedding_service.LLMService"):
            return EmbeddingService(provider="fastembed")

    async def test_generate_fastembed(self, fast_service):
        with patch("fastembed.TextEmbedding") as m_cls:
            emb = Mock()
            emb.tolist.return_value = [0.1, 0.2]
            m_cls.return_value.embed.return_value = [emb]
            result = await fast_service.generate_embedding("hello world")
        assert result == [0.1, 0.2]
        assert fast_service._client is m_cls.return_value
        m_cls.assert_called_once_with(model_name="BAAI/bge-small-en-v1.5")

    async def test_generate_fastembed_reuses_client(self, fast_service):
        emb = Mock()
        emb.tolist.return_value = [0.5]
        client = Mock()
        client.embed.return_value = [emb]
        fast_service._client = client
        with patch("fastembed.TextEmbedding") as m_cls:
            result = await fast_service.generate_embedding("x")
        assert result == [0.5]
        m_cls.assert_not_called()

    async def test_generate_fastembed_empty_result(self, fast_service):
        with patch("fastembed.TextEmbedding") as m_cls:
            m_cls.return_value.embed.return_value = []
            with pytest.raises(Exception, match="empty result"):
                await fast_service.generate_embedding("x")

    async def test_generate_fastembed_import_error(self, fast_service):
        with patch.dict(sys.modules, {"fastembed": None}):
            with pytest.raises(Exception, match="FastEmbed package not installed"):
                await fast_service.generate_embedding("x")

    async def test_generate_fastembed_generic_error(self, fast_service):
        with patch("fastembed.TextEmbedding") as m_cls:
            m_cls.return_value.embed.side_effect = RuntimeError("onnx fail")
            with pytest.raises(RuntimeError, match="onnx fail"):
                await fast_service.generate_embedding("x")

    async def test_generate_openai_via_llm_service(self):
        llm = Mock()
        llm.generate_embedding = AsyncMock(return_value=[0.5, 0.6])
        with patch("core.embedding_service.LLMService", return_value=llm):
            svc = EmbeddingService(provider="openai")
            result = await svc.generate_embedding("text")
        assert result == [0.5, 0.6]
        llm.generate_embedding.assert_awaited_once_with(text="text", model=svc.model)

    async def test_generate_cohere_via_llm_service(self):
        llm = Mock()
        llm.generate_embedding = AsyncMock(return_value=[1.0])
        with patch("core.embedding_service.LLMService", return_value=llm):
            svc = EmbeddingService(provider="cohere")
            await svc.generate_embedding("text")
        llm.generate_embedding.assert_awaited()

    async def test_generate_unknown_provider_raises(self, fast_service):
        fast_service.provider = "weird"
        with pytest.raises(ValueError, match="Unknown provider"):
            await fast_service.generate_embedding("x")

    async def test_generate_reraises_errors(self, fast_service):
        with patch.object(fast_service, "_preprocess_text", side_effect=RuntimeError("prep fail")):
            with pytest.raises(RuntimeError, match="prep fail"):
                await fast_service.generate_embedding("x")

    async def test_generate_batch_fastembed(self, fast_service):
        with patch("fastembed.TextEmbedding") as m_cls:
            e1, e2 = Mock(), Mock()
            e1.tolist.return_value = [1.0]
            e2.tolist.return_value = [2.0]
            m_cls.return_value.embed.return_value = [e1, e2]
            result = await fast_service.generate_embeddings_batch(["a", "b"])
        assert result == [[1.0], [2.0]]
        m_cls.return_value.embed.assert_called_once_with(["a", "b"])

    async def test_generate_batch_openai(self):
        llm = Mock()
        llm.generate_embeddings_batch = AsyncMock(return_value=[[1.0]])
        with patch("core.embedding_service.LLMService", return_value=llm):
            svc = EmbeddingService(provider="openai")
            result = await svc.generate_embeddings_batch(["a"])
        assert result == [[1.0]]
        llm.generate_embeddings_batch.assert_awaited_once_with(texts=["a"], model=svc.model)

    async def test_generate_batch_unknown_provider(self, fast_service):
        fast_service.provider = "weird"
        with pytest.raises(ValueError, match="Unknown provider"):
            await fast_service.generate_embeddings_batch(["a"])

    async def test_generate_batch_reraises(self, fast_service):
        with patch.object(fast_service, "_preprocess_text", side_effect=RuntimeError("prep fail")):
            with pytest.raises(RuntimeError):
                await fast_service.generate_embeddings_batch(["a"])

    async def test_generate_batch_fastembed_error(self, fast_service):
        with patch("fastembed.TextEmbedding") as m_cls:
            m_cls.return_value.embed.side_effect = RuntimeError("batch fail")
            with pytest.raises(RuntimeError, match="batch fail"):
                await fast_service.generate_embeddings_batch(["a"])


class TestEmbeddingPreprocess:
    def _svc(self, provider="fastembed"):
        with patch("core.embedding_service.LLMService"):
            return EmbeddingService(provider=provider)

    def test_empty_text(self):
        assert self._svc()._preprocess_text("") == ""
        assert self._svc()._preprocess_text(None) == ""

    def test_whitespace_collapse(self):
        assert self._svc()._preprocess_text("  hello \n\t world  ") == "hello world"

    def test_unicode_normalization(self):
        assert self._svc()._preprocess_text("\u2161") == "II"

    def test_truncate_fastembed(self):
        svc = self._svc("fastembed")
        assert len(svc._preprocess_text("x" * 10000)) == 8192

    def test_truncate_openai(self):
        svc = self._svc("openai")
        assert len(svc._preprocess_text("x" * 40000)) == 32000

    def test_truncate_cohere(self):
        svc = self._svc("cohere")
        assert len(svc._preprocess_text("x" * 30000)) == 20000

    def test_truncate_unknown_provider_default(self):
        svc = self._svc("fastembed")
        svc.provider = "other"
        assert len(svc._preprocess_text("x" * 9000)) == 8192


class TestFastEmbedCoarseSearch:
    @pytest.fixture
    def svc(self):
        with patch("core.embedding_service.LLMService"):
            return EmbeddingService(provider="fastembed")

    async def test_create_fastembed_embedding_384(self, svc):
        vec = [0.1] * 384
        with patch.object(svc, "_generate_fastembed_embedding", new=AsyncMock(return_value=vec)):
            result = await svc.create_fastembed_embedding("q")
        assert len(result) == 384

    async def test_create_fastembed_embedding_wrong_dim(self, svc):
        with patch.object(svc, "_generate_fastembed_embedding", new=AsyncMock(return_value=[1.0, 2.0])):
            result = await svc.create_fastembed_embedding("q")
        assert len(result) == 2

    async def test_create_fastembed_embedding_no_numpy(self, svc):
        with patch("core.embedding_service.NUMPY_AVAILABLE", False):
            with patch.object(svc, "_generate_fastembed_embedding", new=AsyncMock(return_value=[1.0])):
                result = await svc.create_fastembed_embedding("q")
        assert result == [1.0]

    async def test_create_fastembed_embedding_error(self, svc):
        with patch.object(svc, "_generate_fastembed_embedding", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await svc.create_fastembed_embedding("q") is None

    async def test_cache_and_retrieve_lru(self, svc):
        assert await svc.cache_fastembed_embedding("e1", [1.0, 2.0]) is True
        assert svc.get_cache_stats()["current_size"] == 1
        assert await svc.get_fastembed_embedding("e1") == [1.0, 2.0]
        assert await svc.get_fastembed_embedding("missing") is None

    async def test_cache_with_lancedb_success(self, svc):
        handler = Mock()
        handler.add_embedding = AsyncMock(return_value=True)
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=handler):
            assert await svc.cache_fastembed_embedding("e1", [1.0], db=Mock()) is True
        handler.add_embedding.assert_awaited_once()
        kwargs = handler.add_embedding.call_args.kwargs
        assert kwargs["vector_column"] == "vector_fastembed"

    async def test_cache_with_lancedb_failure(self, svc):
        handler = Mock()
        handler.add_embedding = AsyncMock(side_effect=RuntimeError("lancedb down"))
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=handler):
            assert await svc.cache_fastembed_embedding("e1", [1.0], db=Mock()) is True

    async def test_cache_outer_error(self, svc):
        with patch.object(svc, "_lru_cache_put", side_effect=RuntimeError("boom")):
            assert await svc.cache_fastembed_embedding("e1", [1.0]) is False

    async def test_get_from_lancedb(self, svc):
        handler = Mock()
        handler.get_embedding = AsyncMock(return_value=[0.5, 0.6])
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=handler):
            result = await svc.get_fastembed_embedding("e1", db=Mock())
        assert result == [0.5, 0.6]
        assert svc._fastembed_cache["e1"] == [0.5, 0.6]

    async def test_get_lancedb_miss(self, svc):
        handler = Mock()
        handler.get_embedding = AsyncMock(return_value=None)
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=handler):
            assert await svc.get_fastembed_embedding("e1", db=Mock()) is None

    async def test_get_lancedb_error(self, svc):
        handler = Mock()
        handler.get_embedding = AsyncMock(side_effect=RuntimeError("down"))
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=handler):
            assert await svc.get_fastembed_embedding("e1", db=Mock()) is None

    async def test_get_outer_error(self, svc):
        with patch.object(svc, "_lru_cache_get", side_effect=RuntimeError("boom")):
            assert await svc.get_fastembed_embedding("e1") is None

    async def test_coarse_search_success(self, svc):
        query_vec = [0.1] * 384
        with patch.object(svc, "create_fastembed_embedding", new=AsyncMock(return_value=query_vec)):
            handler = Mock()
            handler.similarity_search = AsyncMock(return_value=[
                {"episode_id": "e1", "score": 0.9},
                {"episode_id": "e2", "score": 0.7},
            ])
            with patch("core.lancedb_handler.get_lancedb_handler", return_value=handler):
                results = await svc.coarse_search_fastembed("a1", "query", top_k=50, db=Mock())
        assert results == [("e1", 0.9), ("e2", 0.7)]
        handler.similarity_search.assert_awaited_once()

    async def test_coarse_search_no_db(self, svc):
        with patch.object(svc, "create_fastembed_embedding", new=AsyncMock(return_value=[0.1] * 384)):
            assert await svc.coarse_search_fastembed("a1", "q") == []

    async def test_coarse_search_no_query_embedding(self, svc):
        with patch.object(svc, "create_fastembed_embedding", new=AsyncMock(return_value=None)):
            assert await svc.coarse_search_fastembed("a1", "q", db=Mock()) == []

    async def test_coarse_search_lancedb_error(self, svc):
        with patch.object(svc, "create_fastembed_embedding", new=AsyncMock(return_value=[0.1] * 384)):
            handler = Mock()
            handler.similarity_search = AsyncMock(side_effect=RuntimeError("down"))
            with patch("core.lancedb_handler.get_lancedb_handler", return_value=handler):
                assert await svc.coarse_search_fastembed("a1", "q", db=Mock()) == []

    async def test_coarse_search_outer_error(self, svc):
        with patch.object(svc, "create_fastembed_embedding", new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert await svc.coarse_search_fastembed("a1", "q") == []

    def test_lru_cache_eviction(self, svc):
        svc._fastembed_cache_max = 2
        svc._lru_cache_put("a", [1.0])
        svc._lru_cache_put("b", [2.0])
        svc._lru_cache_put("c", [3.0])  # evicts "a"
        assert svc._fastembed_cache == {"b": [2.0], "c": [3.0]}
        assert svc._fastembed_cache_order == ["b", "c"]

    def test_lru_cache_duplicate_put(self, svc):
        svc._lru_cache_put("a", [1.0])
        svc._lru_cache_put("a", [9.0])
        assert svc._fastembed_cache_order == ["a"]
        assert svc._fastembed_cache["a"] == [9.0]

    def test_lru_cache_get_moves_to_end(self, svc):
        svc._fastembed_cache_max = 3
        svc._lru_cache_put("a", [1.0])
        svc._lru_cache_put("b", [2.0])
        svc._lru_cache_put("c", [3.0])
        assert svc._lru_cache_get("a") == [1.0]
        assert svc._fastembed_cache_order == ["b", "c", "a"]
        svc._lru_cache_put("d", [4.0])  # evicts "b"
        assert "b" not in svc._fastembed_cache

    def test_cache_stats_empty(self, svc):
        stats = svc.get_cache_stats()
        assert stats["current_size"] == 0
        assert stats["utilization_percent"] == 0.0

    def test_numpy_import_error_fallback(self):
        import core.embedding_service as mod
        with patch.dict(sys.modules, {"numpy": None}):
            importlib.reload(mod)
        try:
            assert mod.NUMPY_AVAILABLE is False
            assert mod.np is None
        finally:
            importlib.reload(mod)
            assert mod.NUMPY_AVAILABLE is True


class TestRerankCrossEncoder:
    def _svc(self):
        with patch("core.embedding_service.LLMService"):
            return EmbeddingService(provider="fastembed")

    def _db_with_episodes(self, episodes):
        db = Mock()
        db.query.return_value.filter.return_value.all.return_value = episodes
        return db

    async def test_rerank_success_sorted(self):
        svc = self._svc()
        episodes = [
            SimpleNamespace(id="e1", task_description="first"),
            SimpleNamespace(id="e2", task_description="second"),
            SimpleNamespace(id="e3", task_description="third"),
        ]
        db = self._db_with_episodes(episodes)
        encoder = Mock()
        encoder.predict.return_value = [0.2, 0.9, 0.5]
        with patch.dict(sys.modules, {
            "sentence_transformers": SimpleNamespace(CrossEncoder=Mock(return_value=encoder)),
        }):
            results = await svc.rerank_cross_encoder("query", ["e1", "e2", "e3"], "a1", db)
        assert results[0][0] == "e2"
        assert results[1][0] == "e3"
        assert results[2][0] == "e1"
        assert svc._cross_encoder is encoder

    async def test_rerank_reuses_encoder(self):
        svc = self._svc()
        svc._cross_encoder = Mock()
        svc._cross_encoder.predict.return_value = [0.5, 0.6]
        episodes = [SimpleNamespace(id="e1", task_description="t"), SimpleNamespace(id="e2", task_description="t2")]
        db = self._db_with_episodes(episodes)
        with patch.dict(sys.modules, {"sentence_transformers": SimpleNamespace(CrossEncoder=Mock(side_effect=AssertionError("must not load")))}):
            results = await svc.rerank_cross_encoder("q", ["e1", "e2"], "a1", db)
        assert len(results) == 2

    async def test_rerank_import_error(self):
        svc = self._svc()
        db = self._db_with_episodes([])
        with patch.dict(sys.modules, {"sentence_transformers": None}):
            assert await svc.rerank_cross_encoder("q", ["e1"], "a1", db) == []

    async def test_rerank_load_error(self):
        svc = self._svc()
        db = self._db_with_episodes([])
        with patch.dict(sys.modules, {
            "sentence_transformers": SimpleNamespace(CrossEncoder=Mock(side_effect=RuntimeError("no model"))),
        }):
            assert await svc.rerank_cross_encoder("q", ["e1"], "a1", db) == []

    async def test_rerank_no_valid_pairs(self):
        svc = self._svc()
        svc._cross_encoder = Mock()
        db = self._db_with_episodes([SimpleNamespace(id="other", task_description="x")])
        assert await svc.rerank_cross_encoder("q", ["e1"], "a1", db) == []

    async def test_rerank_predict_error(self):
        svc = self._svc()
        episodes = [SimpleNamespace(id="e1", task_description="t")]
        db = self._db_with_episodes(episodes)
        encoder = Mock()
        encoder.predict.side_effect = RuntimeError("predict fail")
        with patch.dict(sys.modules, {
            "sentence_transformers": SimpleNamespace(CrossEncoder=Mock(return_value=encoder)),
        }):
            assert await svc.rerank_cross_encoder("q", ["e1"], "a1", db) == []

    async def test_rerank_no_numpy_fallback(self):
        svc = self._svc()
        episodes = [SimpleNamespace(id="e1", task_description="t"), SimpleNamespace(id="e2", task_description="t2")]
        db = self._db_with_episodes(episodes)
        encoder = Mock()
        encoder.predict.return_value = [1.0, 3.0]
        with patch("core.embedding_service.NUMPY_AVAILABLE", False):
            with patch.dict(sys.modules, {
                "sentence_transformers": SimpleNamespace(CrossEncoder=Mock(return_value=encoder)),
            }):
                results = await svc.rerank_cross_encoder("q", ["e1", "e2"], "a1", db)
        assert results[0][0] == "e2"
        assert results[0][1] == pytest.approx(1.0)
        assert results[1][1] == pytest.approx(0.0)


class TestEmbeddingConvenience:
    async def test_generate_embedding_fn(self):
        svc = Mock()
        svc.generate_embedding = AsyncMock(return_value=[1.0])
        with patch("core.embedding_service.EmbeddingService", return_value=svc) as m_cls:
            result = await generate_embedding("text", provider="openai", workspace_id="w", tenant_id="t")
        assert result == [1.0]
        m_cls.assert_called_once_with(provider="openai", workspace_id="w", tenant_id="t")

    async def test_generate_embeddings_batch_fn(self):
        svc = Mock()
        svc.generate_embeddings_batch = AsyncMock(return_value=[[1.0]])
        with patch("core.embedding_service.EmbeddingService", return_value=svc) as m_cls:
            result = await generate_embeddings_batch(["a", "b"])
        assert result == [[1.0]]
        m_cls.assert_called_once_with(provider=None, workspace_id=None, tenant_id=None)


# ===========================================================================
# core/hallucination_config.py
# ===========================================================================


class TestHallucinationFlags:
    @pytest.fixture(autouse=True)
    def clean_env(self):
        with patch.dict(os.environ, {}, clear=True):
            yield

    def test_cascade_routing(self):
        from core.hallucination_config import is_cascade_routing_enabled
        assert is_cascade_routing_enabled() is False
        os.environ["ATOM_CASCADE_ROUTING"] = "true"
        assert is_cascade_routing_enabled() is True

    def test_self_consistency(self):
        from core.hallucination_config import is_self_consistency_enabled
        assert is_self_consistency_enabled() is False
        os.environ["ATOM_SELF_CONSISTENCY"] = "1"
        assert is_self_consistency_enabled() is True

    def test_force_proposal(self):
        from core.hallucination_config import is_self_consistency_force_proposal_enabled
        assert is_self_consistency_force_proposal_enabled() is False
        os.environ["ATOM_SELF_CONSISTENCY_FORCE_PROPOSAL"] = "yes"
        assert is_self_consistency_force_proposal_enabled() is True

    def test_flag_value_variants(self):
        from core.hallucination_config import _flag, _flag_default_true
        for v in ("1", "true", "yes", "on", "True", "YES"):
            os.environ["V"] = v
            assert _flag("V") is True
        for v in ("0", "false", "no", "off", "", "banana"):
            os.environ["V"] = v
            assert _flag("V") is False
        assert _flag("UNSET") is False
        for v in ("0", "false", "no", "off", "FALSE"):
            os.environ["V"] = v
            assert _flag_default_true("V") is False
        os.environ["V"] = "whatever"
        assert _flag_default_true("V") is True
        assert _flag_default_true("UNSET") is True

    def test_skill_injection(self):
        from core.hallucination_config import is_skill_injection_enabled
        assert is_skill_injection_enabled() is True
        os.environ["ATOM_SKILL_INJECTION_ENABLED"] = "false"
        assert is_skill_injection_enabled() is False

    def test_moa(self):
        from core.hallucination_config import is_moa_enabled
        assert is_moa_enabled() is True
        os.environ["ATOM_MOA_ENABLED"] = "off"
        assert is_moa_enabled() is False

    def test_moa_diversity(self):
        from core.hallucination_config import is_moa_diversity_enabled
        assert is_moa_diversity_enabled() is False
        os.environ["ATOM_MOA_DIVERSITY_ENABLED"] = "on"
        assert is_moa_diversity_enabled() is True

    def test_parallel_tools(self):
        from core.hallucination_config import is_parallel_tools_enabled
        assert is_parallel_tools_enabled() is True
        os.environ["ATOM_PARALLEL_TOOLS"] = "0"
        assert is_parallel_tools_enabled() is False

    def test_tool_cache(self):
        from core.hallucination_config import is_tool_cache_enabled
        assert is_tool_cache_enabled() is True
        os.environ["ATOM_TOOL_CACHE_ENABLED"] = "no"
        assert is_tool_cache_enabled() is False

    def test_moa_samples(self):
        from core.hallucination_config import get_moa_samples
        assert get_moa_samples() == 3
        os.environ["ATOM_MOA_SAMPLES"] = "5"
        assert get_moa_samples() == 5
        os.environ["ATOM_MOA_SAMPLES"] = "1"
        assert get_moa_samples() == 2
        os.environ["ATOM_MOA_SAMPLES"] = "abc"
        assert get_moa_samples() == 3
        with patch("core.hallucination_config.os.getenv", return_value=None):
            assert get_moa_samples() == 3

    def test_max_parallel_tools(self):
        from core.hallucination_config import get_max_parallel_tools
        assert get_max_parallel_tools() == 4
        os.environ["ATOM_MAX_PARALLEL_TOOLS"] = "8"
        assert get_max_parallel_tools() == 8
        os.environ["ATOM_MAX_PARALLEL_TOOLS"] = "0"
        assert get_max_parallel_tools() == 1
        os.environ["ATOM_MAX_PARALLEL_TOOLS"] = "zz"
        assert get_max_parallel_tools() == 4
        with patch("core.hallucination_config.os.getenv", return_value=None):
            assert get_max_parallel_tools() == 4

    def test_tool_cache_ttl(self):
        from core.hallucination_config import get_tool_cache_ttl
        assert get_tool_cache_ttl() == 30
        os.environ["ATOM_TOOL_CACHE_TTL"] = "60"
        assert get_tool_cache_ttl() == 60
        os.environ["ATOM_TOOL_CACHE_TTL"] = "-5"
        assert get_tool_cache_ttl() == 0
        os.environ["ATOM_TOOL_CACHE_TTL"] = "bad"
        assert get_tool_cache_ttl() == 30
        with patch("core.hallucination_config.os.getenv", return_value=None):
            assert get_tool_cache_ttl() == 30

    def test_self_consistency_samples(self):
        from core.hallucination_config import get_self_consistency_samples
        assert get_self_consistency_samples() == 3
        os.environ["ATOM_SELF_CONSISTENCY_SAMPLES"] = "5"
        assert get_self_consistency_samples() == 5
        os.environ["ATOM_SELF_CONSISTENCY_SAMPLES"] = "0"
        assert get_self_consistency_samples() == 1
        os.environ["ATOM_SELF_CONSISTENCY_SAMPLES"] = "x"
        assert get_self_consistency_samples() == 3
        with patch("core.hallucination_config.os.getenv", return_value=None):
            assert get_self_consistency_samples() == 3

    def test_high_threshold(self):
        from core.hallucination_config import get_self_consistency_high_threshold
        assert get_self_consistency_high_threshold() == 0.85
        os.environ["ATOM_SELF_CONSISTENCY_HIGH_THRESHOLD"] = "0.9"
        assert get_self_consistency_high_threshold() == 0.9
        os.environ["ATOM_SELF_CONSISTENCY_HIGH_THRESHOLD"] = "bad"
        assert get_self_consistency_high_threshold() == 0.85
        with patch("core.hallucination_config.os.getenv", return_value=None):
            assert get_self_consistency_high_threshold() == 0.85

    def test_partial_threshold(self):
        from core.hallucination_config import get_self_consistency_partial_threshold
        assert get_self_consistency_partial_threshold() == 0.50
        os.environ["ATOM_SELF_CONSISTENCY_PARTIAL_THRESHOLD"] = "0.6"
        assert get_self_consistency_partial_threshold() == 0.6
        os.environ["ATOM_SELF_CONSISTENCY_PARTIAL_THRESHOLD"] = "bad"
        assert get_self_consistency_partial_threshold() == 0.50
        with patch("core.hallucination_config.os.getenv", return_value=None):
            assert get_self_consistency_partial_threshold() == 0.50

    def test_temperature_spread(self):
        from core.hallucination_config import get_temperature_spread
        assert get_temperature_spread(0) == [0.7]
        assert get_temperature_spread(-2) == [0.7]
        assert get_temperature_spread(1) == [0.7]
        assert get_temperature_spread(3) == [0.6, 0.7, 0.8]
        assert get_temperature_spread(5) == [0.5, 0.6, 0.7, 0.8, 0.9]
        assert get_temperature_spread(2) == [0.65, 0.75]
        assert get_temperature_spread(4) == [0.55, 0.65, 0.75, 0.85]


class TestFrontierModels:
    def test_is_frontier_none(self):
        from core.hallucination_config import is_frontier_model
        assert is_frontier_model(None) is False
        assert is_frontier_model("") is False

    def test_is_frontier_exact(self):
        from core.hallucination_config import is_frontier_model
        assert is_frontier_model("gpt-4o") is True
        assert is_frontier_model("claude-3-5-sonnet") is True
        assert is_frontier_model("deepseek-reasoner") is True
        assert is_frontier_model("kimi-k2.6") is True
        assert is_frontier_model("gpt-4o-mini") is False
        assert is_frontier_model("gpt-3.5-turbo") is False
        assert is_frontier_model("GPT-4O") is True

    def test_is_frontier_with_snapshot_suffix(self):
        from core.hallucination_config import is_frontier_model
        assert is_frontier_model("claude-3-opus-20240229") is True
        assert is_frontier_model("claude-3-5-sonnet-20241022") is True
        assert is_frontier_model("gpt-4o-2024-08-06") is True
        assert is_frontier_model("claude-3-opus-2024-08-06") is True

    def test_model_base(self):
        from core.hallucination_config import _model_base
        assert _model_base("claude-3-opus-20240229") == "claude-3-opus"
        assert _model_base("claude-3-5-sonnet-20241022") == "claude-3-5-sonnet"
        assert _model_base("gpt-4o-2024-08-06") == "gpt-4o"
        assert _model_base("deepseek-reasoner") == "deepseek-reasoner"

    def test_frontier_for_provider(self):
        from core.hallucination_config import get_frontier_model_for_provider
        assert get_frontier_model_for_provider(None) is None
        assert get_frontier_model_for_provider("openai") == "gpt-4o"
        assert get_frontier_model_for_provider("anthropic") == "claude-3-5-sonnet"
        assert get_frontier_model_for_provider("LLMProvider.deepseek") == "deepseek-reasoner"
        assert get_frontier_model_for_provider('"gemini"') == "gemini-1.5-pro"
        assert get_frontier_model_for_provider("unknown") is None

    def test_frontier_registry_contents(self):
        from core.hallucination_config import FRONTIER_MODELS, _FRONTIER_BY_PROVIDER
        assert "gpt-4-turbo" in FRONTIER_MODELS
        assert "glm-5.2" in FRONTIER_MODELS
        assert _FRONTIER_BY_PROVIDER["minimax"] == "MiniMax-M3"
        assert _FRONTIER_BY_PROVIDER["zhipu"] == "glm-5.2"
        assert _FRONTIER_BY_PROVIDER["openrouter"] == "anthropic/claude-3.5-sonnet"
        assert _FRONTIER_BY_PROVIDER["ollama"] == "llama3:70b"
