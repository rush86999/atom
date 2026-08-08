"""Coverage push for integrations wave B - batch 5.

slack_workflow_engine / atom_discord_integration / google_chat_enhanced_service /
pdf_ocr_service / pdf_memory_integration. All external I/O mocked.
"""
import asyncio
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


# ============================================================================
# slack_workflow_engine
# ============================================================================


class TestWorkflowEngine:
    def _engine(self):
        from integrations.slack_workflow_engine import WorkflowExecutionEngine
        return WorkflowExecutionEngine({"max_concurrent_executions": 4})

    def _action(self, atype, params=None, **kw):
        from integrations.slack_workflow_engine import WorkflowAction, WorkflowActionParameter
        return WorkflowAction(
            id="a1", type=atype,
            parameters={k: WorkflowActionParameter(name=k, value=v) for k, v in (params or {}).items()},
            **kw,
        )

    def _wf(self):
        from integrations.slack_workflow_engine import (
            WorkflowActionType, WorkflowDefinition, WorkflowTrigger, WorkflowTriggerType,
        )
        return WorkflowDefinition(
            id="wf1", name="W", description="d",
            triggers=[WorkflowTrigger(id="t1", type=WorkflowTriggerType.MESSAGE, conditions=[])],
            actions=[self._action(WorkflowActionType.CREATE_TASK, {"title": "t"})],
            created_by="u", created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def _execution(self, **kw):
        from integrations.slack_workflow_engine import (
            WorkflowExecution, WorkflowExecutionPriority, WorkflowExecutionStatus,
            WorkflowTriggerType,
        )
        return WorkflowExecution(
            id=kw.get("id", "e1"), workflow_id="wf1",
            trigger_type=WorkflowTriggerType.MESSAGE, trigger_data={},
            status=WorkflowExecutionStatus.PENDING,
            priority=WorkflowExecutionPriority.NORMAL,
            started_at=datetime.now(timezone.utc),
        )

    async def test_templates(self):
        from integrations.slack_workflow_engine import WorkflowTemplate
        wf = WorkflowTemplate.welcome_message()
        assert wf.id == "welcome_message_template"
        assert wf.created_at.tzinfo is not None
        wf2 = WorkflowTemplate.message_summary()
        assert wf2.id == "message_summary_template"
        assert wf2.actions[1].delay == 60
        # naive datetime normalization
        wf3 = self._wf()
        wf3.created_at = datetime.now()
        wf3.updated_at = datetime.now()
        from integrations.slack_workflow_engine import WorkflowDefinition
        WorkflowDefinition(**{**{f: getattr(wf3, f) for f in wf3.__dataclass_fields__}})
        ex = self._execution()
        assert ex.action_results == []
        assert ex.logs == []
        ex.completed_at = datetime.now()
        ex2 = self._execution(id="e2")
        ex2.completed_at = datetime.now()

    async def test_execute_workflow_and_worker(self):
        eng = self._engine()
        wf = self._wf()
        exec_id = await eng.execute_workflow(wf, {"type": "message"}, priority=__import__("integrations.slack_workflow_engine", fromlist=["WorkflowExecutionPriority"]).WorkflowExecutionPriority.HIGH)
        assert exec_id.startswith("exec_")
        # drain the queue manually
        with patch.object(eng, "_get_workflow_definition", new=AsyncMock(return_value=wf)):
            while not eng.execution_queue.empty():
                prio, ex = await eng.execution_queue.get()
                task = asyncio.create_task(eng._execute_workflow_instance(ex))
                await task
                assert ex.status.value == "completed"
        assert eng.get_execution_status(exec_id) is not None
        assert eng.get_execution_status("nope") is None
        assert eng.get_workflow_executions("wf1")
        stats = eng.get_execution_stats()
        assert stats["total_executions"] >= 1
        assert eng.cancel_execution("nope") is False
        await eng.cleanup()

    async def test_worker_loop(self):
        eng = self._engine()
        await eng.start_execution_workers(num_workers=1)
        await asyncio.sleep(0.05)
        wf = self._wf()
        await eng.execute_workflow(wf, {"type": "message"})
        await asyncio.sleep(0.3)
        assert eng.execution_history
        # max concurrent -> re-queue path
        eng.max_concurrent_executions = 0
        eng2 = self._engine()
        await eng2.start_execution_workers(num_workers=1)
        await asyncio.sleep(0.05)

    async def test_execution_flow_success(self):
        eng = self._engine()
        wf = self._wf()
        ex = self._execution()
        with patch.object(eng, "_get_workflow_definition", new=AsyncMock(return_value=wf)):
            result = await eng._execute_workflow_instance(ex)
        assert result.status.value == "completed"
        assert result.completed_at is not None

    async def test_execution_flow_missing_workflow(self):
        eng = self._engine()
        ex = self._execution()
        result = await eng._execute_workflow_instance(ex)
        assert result.status.value == "failed"
        assert "not found" in result.error_message

    async def test_execution_action_timeout_and_error(self):
        eng = self._engine()
        wf = self._wf()
        wf.actions = [self._action(__import__("integrations.slack_workflow_engine", fromlist=["WorkflowActionType"]).WorkflowActionType.CREATE_TASK, {"title": "t"}, timeout=0.01, continue_on_error=True)]
        ex = self._execution()
        with patch.object(eng, "_get_workflow_definition", new=AsyncMock(return_value=wf)), \
             patch.object(eng, "_execute_action", new=AsyncMock(side_effect=asyncio.TimeoutError())):
            result = await eng._execute_workflow_instance(ex)
        assert result.status.value == "completed"
        assert result.action_results[0]["status"] == "timeout"
        # error with continue_on_error
        ex2 = self._execution(id="e2")
        with patch.object(eng, "_get_workflow_definition", new=AsyncMock(return_value=wf)), \
             patch.object(eng, "_execute_action", new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await eng._execute_workflow_instance(ex2)
        assert result.status.value == "completed"
        assert result.action_results[0]["status"] == "failed"
        # without continue_on_error -> whole execution fails
        wf.actions[0].continue_on_error = False
        ex3 = self._execution(id="e3")
        with patch.object(eng, "_get_workflow_definition", new=AsyncMock(return_value=wf)), \
             patch.object(eng, "_execute_action", new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await eng._execute_workflow_instance(ex3)
        assert result.status.value == "failed"

    async def test_execution_delay(self):
        eng = self._engine()
        from integrations.slack_workflow_engine import WorkflowActionType
        wf = self._wf()
        wf.actions = [self._action(WorkflowActionType.CREATE_TASK, {"title": "t"}, delay=1)]
        ex = self._execution()
        with patch.object(eng, "_get_workflow_definition", new=AsyncMock(return_value=wf)), \
             patch("asyncio.sleep", new=AsyncMock()):
            result = await eng._execute_workflow_instance(ex)
        assert result.status.value == "completed"
        assert any("delay" in l["message"] for l in result.logs)

    async def test_variables_and_templates(self):
        eng = self._engine()
        wf = self._wf()
        wf.actions = [self._action(__import__("integrations.slack_workflow_engine", fromlist=["WorkflowActionType"]).WorkflowActionType.CREATE_TASK,
                                   {"title": "{{trigger.user}} - {{workflow_name}}"}, delay=0)]
        ex = self._execution()
        await eng._process_variables(ex, wf, {"user": "bob"})
        assert "bob" in wf.actions[0].parameters["title"].value
        assert await eng._substitute_template("x {{a.b}} y", {"a": {"b": 1}}) == "x 1 y"
        assert await eng._substitute_template("x {{missing}} y", {}) == "x  y"
        assert eng._get_nested_variable({"a": {"b": 1}}, "a.b") == 1
        assert eng._get_nested_variable({"a": 1}, "a.b") is None
        assert eng._get_nested_variable(None, "a") is None
        assert eng._should_execute_action(ex, wf.actions[0]) is True

    async def test_action_handlers_mock_paths(self):
        eng = self._engine()
        eng.slack_service = None
        ex = self._execution()
        from integrations.slack_workflow_engine import WorkflowActionType
        results = {}
        results["send"] = await eng._handle_send_message(ex, self._action(WorkflowActionType.SEND_MESSAGE, {"channel": "C", "message": "m"}))
        assert results["send"]["method"] == "mock"
        results["dm"] = await eng._handle_send_dm(ex, self._action(WorkflowActionType.SEND_DM, {"user_id": "U", "message": "m"}))
        assert results["dm"]["method"] == "mock"
        results["ch"] = await eng._handle_create_channel(ex, self._action(WorkflowActionType.CREATE_CHANNEL, {"name": "n", "private": False, "description": "d"}))
        assert results["ch"]["method"] == "mock"
        results["inv"] = await eng._handle_invite_user(ex, self._action(WorkflowActionType.INVITE_USER, {"channel": "C", "user_ids": "U1"}))
        assert results["inv"]["method"] == "mock"
        results["inv2"] = await eng._handle_invite_user(ex, self._action(WorkflowActionType.INVITE_USER, {"channel": "C", "user_ids": ["U1", "U2"]}))
        assert results["inv2"]["method"] == "mock"
        results["re"] = await eng._handle_add_reaction(ex, self._action(WorkflowActionType.ADD_REACTION, {"channel": "C", "message_ts": "1", "emoji": ":x:"}))
        assert results["re"]["method"] == "mock"
        results["pin"] = await eng._handle_pin_message(ex, self._action(WorkflowActionType.PIN_MESSAGE, {"channel": "C", "message_ts": "1"}))
        assert results["pin"]["method"] == "mock"
        results["task"] = await eng._handle_create_task(ex, self._action(WorkflowActionType.CREATE_TASK, {"title": "t", "description": "d", "assignee": "a"}))
        assert results["task"]["status"] == "open"
        results["st"] = await eng._handle_update_status(ex, self._action(WorkflowActionType.UPDATE_STATUS, {"status": "s", "emoji": "e"}))
        assert results["st"]["status_text"] == "s"
        results["api"] = await eng._handle_call_api(ex, self._action(WorkflowActionType.CALL_API, {"endpoint": "/x", "method": "GET"}))
        assert results["api"]["status_code"] == 200
        results["mail"] = await eng._handle_send_email(ex, self._action(WorkflowActionType.SEND_EMAIL, {"to": "a@b.c", "subject": "s", "body": "b"}))
        assert results["mail"]["to"] == "a@b.c"
        results["script"] = await eng._handle_execute_script(ex, self._action(WorkflowActionType.EXECUTE_SCRIPT, {"script": "s", "args": []}))
        assert results["script"]["exit_code"] == 0
        results["sheet"] = await eng._handle_update_spreadsheet(ex, self._action(WorkflowActionType.UPDATE_SPREADSHEET, {"spreadsheet_id": "s", "range": "A1", "values": [1, 2]}))
        assert results["sheet"]["updated_cells"] == 2
        results["meet"] = await eng._handle_create_meeting(ex, self._action(WorkflowActionType.CREATE_MEETING, {"title": "t", "attendees": [], "start_time": "1", "duration": 30}))
        assert results["meet"]["title"] == "t"
        with pytest.raises(ValueError):
            await eng._handle_unknown_action(ex, self._action(WorkflowActionType.CREATE_TASK, {}))

    async def test_action_handlers_with_service_success(self):
        eng = self._engine()
        svc = MagicMock()
        svc.send_message = AsyncMock(return_value={"ok": True, "timestamp": "1", "message_id": "m1"})
        svc.send_dm = AsyncMock(return_value={"ok": True, "timestamp": "1", "message_id": "m1"})
        svc.create_channel = AsyncMock(return_value={"ok": True, "channel_id": "C2"})
        svc.invite_to_channel = AsyncMock(return_value={"invited_users": ["U1"], "failed_users": []})
        svc.add_reaction = AsyncMock(return_value={"ok": True})
        svc.pin_message = AsyncMock(return_value={"ok": True})
        eng.slack_service = svc
        ex = self._execution()
        ex.trigger_data = {"workspace_id": "ws"}
        from integrations.slack_workflow_engine import WorkflowActionType
        r = await eng._handle_send_message(ex, self._action(WorkflowActionType.SEND_MESSAGE, {"channel": "C", "message": "m"}))
        assert r["method"] == "slack_api"
        r = await eng._handle_send_dm(ex, self._action(WorkflowActionType.SEND_DM, {"user_id": "U", "message": "m"}))
        assert r["method"] == "slack_api"
        r = await eng._handle_create_channel(ex, self._action(WorkflowActionType.CREATE_CHANNEL, {"name": "n", "private": False, "description": "d"}))
        assert r["method"] == "slack_api"
        r = await eng._handle_invite_user(ex, self._action(WorkflowActionType.INVITE_USER, {"channel": "C", "user_ids": ["U1"]}))
        assert r["method"] == "slack_api"
        r = await eng._handle_add_reaction(ex, self._action(WorkflowActionType.ADD_REACTION, {"channel": "C", "message_ts": "1", "emoji": "e"}))
        assert r["method"] == "slack_api"
        r = await eng._handle_pin_message(ex, self._action(WorkflowActionType.PIN_MESSAGE, {"channel": "C", "message_ts": "1"}))
        assert r["method"] == "slack_api"
        # service failure falls back to mock
        svc.send_message = AsyncMock(side_effect=RuntimeError("x"))
        r = await eng._handle_send_message(ex, self._action(WorkflowActionType.SEND_MESSAGE, {"channel": "C", "message": "m"}))
        assert r["method"] == "mock"
        svc.send_message = AsyncMock(return_value={"ok": False})
        r = await eng._handle_send_message(ex, self._action(WorkflowActionType.SEND_MESSAGE, {"channel": "C", "message": "m"}))
        assert r["method"] == "mock"

    async def test_log_and_stats(self):
        eng = self._engine()
        ex = self._execution()
        eng._log_execution(ex, "info", "msg")
        eng._log_execution(ex, "debug", "msg")
        for i in range(105):
            eng._log_execution(ex, "info", f"m{i}")
        assert len(ex.logs) <= 100
        ex.status = __import__("integrations.slack_workflow_engine", fromlist=["WorkflowExecutionStatus"]).WorkflowExecutionStatus.COMPLETED
        ex.completed_at = datetime.now(timezone.utc)
        eng._update_execution_stats(ex)
        assert eng.execution_stats["successful_executions"] == 1
        ex2 = self._execution(id="e2")
        ex2.status = __import__("integrations.slack_workflow_engine", fromlist=["WorkflowExecutionStatus"]).WorkflowExecutionStatus.FAILED
        ex2.completed_at = datetime.now(timezone.utc)
        eng._update_execution_stats(ex2)
        assert eng.execution_stats["failed_executions"] == 1
        assert eng.execution_stats["average_execution_time"] >= 0
        assert eng.get_execution_stats()["total_executions"] == 2

    async def test_execute_workflow_error_path(self):
        eng = self._engine()
        with patch.object(eng.execution_queue, "put", new=AsyncMock(side_effect=RuntimeError("x"))):
            with pytest.raises(RuntimeError):
                await eng.execute_workflow(self._wf(), {})
        assert eng.execution_history == []

    async def test_module_instance(self):
        import integrations.slack_workflow_engine as mod
        assert mod.workflow_engine is not None
        assert mod.workflow_engine.get_execution_stats() is not None


class TestWorkflowEngineGaps:
    def _engine(self, **kw):
        from integrations.slack_workflow_engine import WorkflowExecutionEngine
        cfg = {"max_concurrent_executions": 4}
        cfg.update(kw)
        return WorkflowExecutionEngine(cfg)

    def _action(self, atype, params=None, **kw):
        from integrations.slack_workflow_engine import WorkflowAction, WorkflowActionParameter
        return WorkflowAction(
            id="a1", type=atype,
            parameters={k: WorkflowActionParameter(name=k, value=v) for k, v in (params or {}).items()},
            **kw,
        )

    def _wf(self):
        from integrations.slack_workflow_engine import (
            WorkflowActionType, WorkflowDefinition, WorkflowTrigger, WorkflowTriggerType,
        )
        return WorkflowDefinition(
            id="wf1", name="W", description="d",
            triggers=[WorkflowTrigger(id="t1", type=WorkflowTriggerType.MESSAGE, conditions=[])],
            actions=[self._action(WorkflowActionType.CREATE_TASK, {"title": "t"})],
            created_by="u", created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def _execution(self, **kw):
        from integrations.slack_workflow_engine import (
            WorkflowExecution, WorkflowExecutionPriority, WorkflowExecutionStatus,
            WorkflowTriggerType,
        )
        return WorkflowExecution(
            id=kw.get("id", "e1"), workflow_id="wf1",
            trigger_type=WorkflowTriggerType.MESSAGE, trigger_data={},
            status=WorkflowExecutionStatus.PENDING,
            priority=WorkflowExecutionPriority.NORMAL,
            started_at=datetime.now(timezone.utc),
        )

    async def test_naive_datetime_normalization(self):
        from integrations.slack_workflow_engine import (
            WorkflowExecution, WorkflowExecutionPriority, WorkflowExecutionStatus,
            WorkflowTriggerType,
        )
        ex = WorkflowExecution(
            id="e", workflow_id="w", trigger_type=WorkflowTriggerType.MESSAGE,
            trigger_data={}, status=WorkflowExecutionStatus.PENDING,
            priority=WorkflowExecutionPriority.NORMAL,
            started_at=datetime.now(), completed_at=datetime.now(),
        )
        assert ex.started_at.tzinfo is not None

    async def test_engine_init_failure_fallback(self):
        import integrations.slack_workflow_engine as mod
        with patch.object(mod.SlackEnhancedService, "__init__", side_effect=RuntimeError("x")):
            eng = self._engine(slack={"token": "x"})
        assert eng.slack_service is None

    async def test_register_handler(self):
        from integrations.slack_workflow_engine import WorkflowActionType
        eng = self._engine()
        handler = MagicMock()
        await eng.register_action_handler(WorkflowActionType.CREATE_TASK, handler)
        assert eng.action_handlers[WorkflowActionType.CREATE_TASK] is handler

    async def test_worker_default_and_requeue_and_error(self):
        eng = self._engine()
        eng.max_concurrent_executions = 0
        real_sleep = asyncio.sleep

        async def short_sleep(delay):
            await real_sleep(0.001)

        with patch("asyncio.sleep", side_effect=short_sleep):
            await eng.start_execution_workers()  # default num_workers
            wf = self._wf()
            await eng.execute_workflow(wf, {"type": "message"})
            await real_sleep(0.05)
            assert not eng.execution_queue.empty()
        # worker error branch
        eng2 = self._engine()
        with patch.object(eng2.execution_queue, "get",
                          new=AsyncMock(side_effect=RuntimeError("x"))), \
             patch("asyncio.sleep", side_effect=short_sleep):
            worker = asyncio.create_task(eng2._execution_worker("w"))
            await real_sleep(0.05)
            worker.cancel()

    async def test_timeout_without_continue(self):
        from integrations.slack_workflow_engine import WorkflowActionType
        eng = self._engine()
        wf = self._wf()
        wf.actions = [self._action(WorkflowActionType.CREATE_TASK, {"title": "t"}, timeout=0.01)]
        ex = self._execution()
        with patch.object(eng, "_get_workflow_definition", new=AsyncMock(return_value=wf)), \
             patch.object(eng, "_execute_action", new=AsyncMock(side_effect=asyncio.TimeoutError())):
            result = await eng._execute_workflow_instance(ex)
        assert result.status.value == "failed"

    async def test_history_trim(self):
        eng = self._engine()
        eng.execution_history = [MagicMock() for _ in range(1001)]
        wf = self._wf()
        ex = self._execution(id="trim")
        with patch.object(eng, "_get_workflow_definition", new=AsyncMock(return_value=wf)):
            await eng._execute_workflow_instance(ex)
        assert len(eng.execution_history) <= 1000

    async def test_substitute_and_nested_excepts(self):
        eng = self._engine()
        with patch("re.sub", side_effect=RuntimeError("x")):
            assert await eng._substitute_template("t", {}) == "t"

        class BadDict(dict):
            def __contains__(self, k):
                raise RuntimeError("x")
        assert eng._get_nested_variable(BadDict(), "a") is None

    async def test_execute_action_no_handler(self):
        from integrations.slack_workflow_engine import WorkflowActionType
        eng = self._engine()
        eng.action_handlers = {}
        with pytest.raises(ValueError):
            await eng._execute_action(self._execution(),
                                      self._action(WorkflowActionType.CREATE_TASK, {}))

    async def test_handler_service_failures(self):
        from integrations.slack_workflow_engine import WorkflowActionType
        eng = self._engine()
        svc = MagicMock()
        eng.slack_service = svc
        ex = self._execution()
        ex.trigger_data = {"workspace_id": "ws"}
        for name, atype, params, mock_name in [
            ("send_message", WorkflowActionType.SEND_MESSAGE, {"channel": "C", "message": "m"}, "send_message"),
            ("send_dm", WorkflowActionType.SEND_DM, {"user_id": "U", "message": "m"}, "send_dm"),
            ("create_channel", WorkflowActionType.CREATE_CHANNEL, {"name": "n", "private": False, "description": "d"}, "create_channel"),
            ("invite_user", WorkflowActionType.INVITE_USER, {"channel": "C", "user_ids": ["U1"]}, "invite_to_channel"),
            ("add_reaction", WorkflowActionType.ADD_REACTION, {"channel": "C", "message_ts": "1", "emoji": "e"}, "add_reaction"),
            ("pin_message", WorkflowActionType.PIN_MESSAGE, {"channel": "C", "message_ts": "1"}, "pin_message"),
        ]:
            setattr(svc, mock_name, AsyncMock(side_effect=RuntimeError("x")))
            handler = getattr(eng, f"_handle_{name}")
            result = await handler(ex, self._action(atype, params))
            assert result["method"] == "mock", name
        # ok=False fallback paths
        svc.send_dm = AsyncMock(return_value={"ok": False})
        result = await eng._handle_send_dm(ex, self._action(WorkflowActionType.SEND_DM, {"user_id": "U", "message": "m"}))
        assert result["method"] == "mock"
        svc.create_channel = AsyncMock(return_value={"ok": False})
        result = await eng._handle_create_channel(ex, self._action(WorkflowActionType.CREATE_CHANNEL, {"name": "n", "private": False, "description": "d"}))
        assert result["method"] == "mock"
        svc.add_reaction = AsyncMock(return_value={"ok": False})
        result = await eng._handle_add_reaction(ex, self._action(WorkflowActionType.ADD_REACTION, {"channel": "C", "message_ts": "1", "emoji": "e"}))
        assert result["method"] == "mock"
        svc.pin_message = AsyncMock(return_value={"ok": False})
        result = await eng._handle_pin_message(ex, self._action(WorkflowActionType.PIN_MESSAGE, {"channel": "C", "message_ts": "1"}))
        assert result["method"] == "mock"

    async def test_running_execution_status_cancel_cleanup(self):
        eng = self._engine()
        task = asyncio.create_task(asyncio.sleep(30))
        eng.running_executions["rx"] = task
        status = eng.get_execution_status("rx")
        assert status.status.value == "running"
        assert eng.cancel_execution("rx") is True
        assert eng.cancel_execution("rx") is False
        task2 = asyncio.create_task(asyncio.sleep(30))
        eng.running_executions["ry"] = task2
        await eng.cleanup()
        assert eng.running_executions == {}


class TestWorkflowEngineWorkerBranches:
    async def test_requeue_and_error_continue(self):
        import integrations.slack_workflow_engine as mod
        eng = mod.WorkflowExecutionEngine({"max_concurrent_executions": 1})
        wf = __import__("tests.test_covpush_intgr_b5", fromlist=["TestWorkflowEngineGaps"]).TestWorkflowEngineGaps()._wf()
        real_sleep = asyncio.sleep

        async def short_sleep(delay):
            await real_sleep(0.002)

        await eng.start_execution_workers(num_workers=1)
        await eng.execute_workflow(wf, {"type": "message"})
        await real_sleep(0.05)
        eng.max_concurrent_executions = 0
        await eng.execute_workflow(wf, {"type": "message"})
        await real_sleep(0.05)
        assert not eng.execution_queue.empty() or eng.running_executions
        # error-continue branch
        eng2 = mod.WorkflowExecutionEngine({"max_concurrent_executions": 1})
        with patch.object(eng2.execution_queue, "get", new=AsyncMock(side_effect=RuntimeError("x"))), \
             patch("asyncio.sleep", side_effect=short_sleep):
            worker = asyncio.create_task(eng2._execution_worker("w"))
            await real_sleep(0.05)
            worker.cancel()
            with pytest.raises(asyncio.CancelledError):
                await worker
