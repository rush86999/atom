"""Coverage push + bug-fix tests for integrations.slack_workflow_engine.

Covers DAG execution (delays, timeouts, retries, continue-on-error), all
action handlers, template substitution, worker/queue behavior, stats, and
execution lifecycle. SlackEnhancedService calls mocked.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integrations.slack_workflow_engine import (
    WorkflowAction,
    WorkflowActionParameter,
    WorkflowActionType,
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowExecutionEngine,
    WorkflowExecutionPriority,
    WorkflowExecutionStatus,
    WorkflowTemplate,
    WorkflowTrigger,
    WorkflowTriggerType,
)


def _execution(**kw):
    data = dict(
        id="exec-1", workflow_id="wf-1", trigger_type=WorkflowTriggerType.MESSAGE,
        trigger_data={"type": "message", "workspace_id": "T1"},
        status=WorkflowExecutionStatus.PENDING,
        priority=WorkflowExecutionPriority.NORMAL,
        started_at=datetime.now(timezone.utc),
    )
    data.update(kw)
    return WorkflowExecution(**data)


def _action(action_type, params=None, **kw):
    return WorkflowAction(
        id=f"action-{action_type.value}", type=action_type,
        parameters=params or {}, **kw)


def _param(name, value, **kw):
    return WorkflowActionParameter(name=name, value=value, **kw)


def _workflow(actions=None, **kw):
    data = dict(
        id="wf-1", name="test workflow", description="d",
        triggers=[], actions=actions or [],
        created_by="u1", created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        variables={"team_id": "T-ACME"},
    )
    data.update(kw)
    return WorkflowDefinition(**data)


def _engine(**cfg):
    base = {"max_concurrent_executions": 4, "execution_timeout": 30}
    base.update(cfg)
    engine = WorkflowExecutionEngine(base)
    engine.slack_service = None
    return engine


class TestDataclassDefaults:
    def test_workflow_definition_naive_datetimes(self):
        now = datetime.now()
        wf = WorkflowDefinition(
            id="w", name="n", description="d", triggers=[], actions=[],
            created_by="u", created_at=now, updated_at=now)
        assert wf.created_at.tzinfo is not None
        assert wf.variables == {}
        assert wf.settings == {}
        assert wf.tags == []

    def test_workflow_execution_naive_datetimes(self):
        now = datetime.now()
        exec_ = WorkflowExecution(
            id="e", workflow_id="w", trigger_type=WorkflowTriggerType.MESSAGE,
            trigger_data={}, status=WorkflowExecutionStatus.PENDING,
            priority=WorkflowExecutionPriority.NORMAL, started_at=now,
            completed_at=now)
        assert exec_.started_at.tzinfo is not None
        assert exec_.completed_at.tzinfo is not None
        assert exec_.execution_context == {}
        assert exec_.action_results == []
        assert exec_.variables == {}
        assert exec_.logs == []

    def test_templates(self):
        welcome = WorkflowTemplate.welcome_message()
        assert welcome.category == "onboarding"
        assert welcome.triggers[0].type == WorkflowTriggerType.USER_JOINED
        summary = WorkflowTemplate.message_summary()
        assert summary.triggers[0].schedule == "0 18 * * 1-5"
        assert len(summary.actions) == 2


class TestEngineInit:
    def test_slack_service_init_failure(self):
        with patch("integrations.slack_workflow_engine.SlackEnhancedService",
                   side_effect=RuntimeError("no creds")):
            engine = WorkflowExecutionEngine({"slack": {"client_id": "x"}})
        assert engine.slack_service is None

    def test_default_handler_mapping(self):
        engine = _engine()
        for action_type in WorkflowActionType:
            assert engine.action_handlers[action_type] is not None


class TestExecuteWorkflow:
    async def test_execute_workflow_queues(self):
        engine = _engine()
        wf = _workflow()
        execution_id = await engine.execute_workflow(wf, {"type": "message"})
        assert execution_id.startswith("exec_")
        priority_value, execution = engine.execution_queue.get_nowait()
        assert priority_value == WorkflowExecutionPriority.NORMAL.value
        assert execution.id == execution_id
        assert execution.execution_context["workflow_name"] == "test workflow"

    async def test_execute_workflow_invalid_trigger_raises(self):
        engine = _engine()
        wf = _workflow()
        with pytest.raises(ValueError):
            await engine.execute_workflow(wf, {"type": "bogus-type"})

    async def test_execute_workflow_with_high_priority(self):
        engine = _engine()
        wf = _workflow()
        await engine.execute_workflow(
            wf, {"type": "scheduled"}, WorkflowExecutionPriority.CRITICAL)
        priority_value, _ = engine.execution_queue.get_nowait()
        assert priority_value == WorkflowExecutionPriority.CRITICAL.value


class TestWorkers:
    async def test_start_execution_workers(self):
        engine = _engine()

        def _discard(coro):
            coro.close()
            return MagicMock()

        with patch("integrations.slack_workflow_engine.asyncio.create_task",
                   side_effect=_discard) as create_task:
            await engine.start_execution_workers(num_workers=2)
        assert create_task.call_count == 2

    async def test_start_execution_workers_default_count(self):
        engine = _engine()

        def _discard(coro):
            coro.close()
            return MagicMock()

        with patch("integrations.slack_workflow_engine.asyncio.create_task",
                   side_effect=_discard) as create_task:
            await engine.start_execution_workers()
        assert create_task.call_count == min(engine.max_concurrent_executions, 4)

    async def test_worker_processes_queue(self):
        engine = _engine()
        engine._get_workflow_definition = AsyncMock(return_value=_workflow())
        execution = _execution()
        await engine.execution_queue.put((2, execution))
        worker = asyncio.create_task(engine._execution_worker("w1"))
        for _ in range(100):
            if engine.execution_history:
                break
            await asyncio.sleep(0.02)
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass
        assert engine.execution_history[0].id == execution.id
        assert engine.execution_history[0].status == WorkflowExecutionStatus.COMPLETED

    async def test_worker_max_concurrency_waits(self):
        engine = _engine()
        engine.max_concurrent_executions = 1
        engine.running_executions["busy"] = asyncio.create_task(asyncio.sleep(30))
        execution = _execution()
        await engine.execution_queue.put((2, execution))
        worker = asyncio.create_task(engine._execution_worker("w1"))
        await asyncio.sleep(1.6)
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass
        engine.running_executions["busy"].cancel()
        assert not engine.execution_history
        assert engine.execution_queue.qsize() == 1

    async def test_worker_handles_queue_error(self):
        engine = _engine()
        engine.execution_queue.get = AsyncMock(side_effect=RuntimeError("queue down"))
        worker = asyncio.create_task(engine._execution_worker("w1"))
        await asyncio.sleep(0.05)
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass


class TestExecuteWorkflowInstance:
    async def test_successful_execution(self):
        engine = _engine()
        actions = [
            _action(WorkflowActionType.SEND_MESSAGE, {
                "channel": _param("channel", "C1"),
                "message": _param("message", "hello {{trigger.user_id}}"),
            }),
            _action(WorkflowActionType.CREATE_TASK, {
                "title": _param("title", "Do it"),
                "description": _param("description", "desc"),
                "assignee": _param("assignee", "U1"),
            }),
        ]
        wf = _workflow(actions=actions)
        engine._get_workflow_definition = AsyncMock(return_value=wf)
        execution = _execution()
        result = await engine._execute_workflow_instance(execution)
        assert result.status == WorkflowExecutionStatus.COMPLETED
        assert len(result.action_results) == 2
        assert result.action_results[0]["status"] == "success"
        assert result.variables["workflow_name"] == "test workflow"
        assert engine.execution_stats["successful_executions"] == 1
        assert engine.execution_stats["total_executions"] == 1

    async def test_execution_applies_delay(self):
        engine = _engine()
        wf = _workflow(actions=[
            _action(WorkflowActionType.CREATE_TASK,
                    {"title": _param("title", "T")}, delay=1),
        ])
        engine._get_workflow_definition = AsyncMock(return_value=wf)
        result = await engine._execute_workflow_instance(_execution())
        assert result.status == WorkflowExecutionStatus.COMPLETED
        assert any("delay" in log["message"] for log in result.logs)

    async def test_missing_workflow_definition_fails(self):
        engine = _engine()
        engine._get_workflow_definition = AsyncMock(return_value=None)
        result = await engine._execute_workflow_instance(_execution())
        assert result.status == WorkflowExecutionStatus.FAILED
        assert "not found" in result.error_message

    async def test_action_timeout_continue_on_error(self):
        engine = _engine()

        async def slow_handler(execution, action):
            await asyncio.sleep(10)

        engine.action_handlers[WorkflowActionType.CREATE_TASK] = slow_handler
        wf = _workflow(actions=[
            _action(WorkflowActionType.CREATE_TASK,
                    {"title": _param("title", "T")}, timeout=1, continue_on_error=True),
        ])
        engine._get_workflow_definition = AsyncMock(return_value=wf)
        result = await engine._execute_workflow_instance(_execution())
        assert result.status == WorkflowExecutionStatus.COMPLETED
        assert result.action_results[0]["status"] == "timeout"

    async def test_action_timeout_fails_execution(self):
        engine = _engine()

        async def slow_handler(execution, action):
            await asyncio.sleep(10)

        engine.action_handlers[WorkflowActionType.CREATE_TASK] = slow_handler
        wf = _workflow(actions=[
            _action(WorkflowActionType.CREATE_TASK,
                    {"title": _param("title", "T")}, timeout=1),
        ])
        engine._get_workflow_definition = AsyncMock(return_value=wf)
        result = await engine._execute_workflow_instance(_execution())
        assert result.status == WorkflowExecutionStatus.FAILED
        assert "timed out" in result.error_message

    async def test_action_error_continue_on_error(self):
        engine = _engine()

        async def failing_handler(execution, action):
            raise RuntimeError("handler exploded")

        engine.action_handlers[WorkflowActionType.CREATE_TASK] = failing_handler
        wf = _workflow(actions=[
            _action(WorkflowActionType.CREATE_TASK,
                    {"title": _param("title", "T")}, continue_on_error=True),
        ])
        engine._get_workflow_definition = AsyncMock(return_value=wf)
        result = await engine._execute_workflow_instance(_execution())
        assert result.status == WorkflowExecutionStatus.COMPLETED
        assert result.action_results[0]["status"] == "failed"

    async def test_action_error_fails_execution(self):
        engine = _engine()

        async def failing_handler(execution, action):
            raise RuntimeError("handler exploded")

        engine.action_handlers[WorkflowActionType.CREATE_TASK] = failing_handler
        wf = _workflow(actions=[
            _action(WorkflowActionType.CREATE_TASK, {"title": _param("title", "T")}),
        ])
        engine._get_workflow_definition = AsyncMock(return_value=wf)
        result = await engine._execute_workflow_instance(_execution())
        assert result.status == WorkflowExecutionStatus.FAILED
        assert engine.execution_stats["failed_executions"] == 1

    async def test_action_skipped_when_condition_false(self):
        engine = _engine()
        engine._should_execute_action = MagicMock(return_value=False)
        wf = _workflow(actions=[
            _action(WorkflowActionType.CREATE_TASK, {"title": _param("title", "T")}),
        ])
        engine._get_workflow_definition = AsyncMock(return_value=wf)
        result = await engine._execute_workflow_instance(_execution())
        assert result.status == WorkflowExecutionStatus.COMPLETED
        assert result.action_results == []

    async def test_history_capped_at_1000(self):
        engine = _engine()
        engine._get_workflow_definition = AsyncMock(return_value=_workflow())
        for i in range(1001):
            result = await engine._execute_workflow_instance(
                _execution(id=f"exec-{i}", workflow_id=f"wf-{i}"))
            assert result.status in (
                WorkflowExecutionStatus.COMPLETED, WorkflowExecutionStatus.FAILED)
        assert len(engine.execution_history) == 1000
        assert engine.execution_history[0].id == "exec-1"

    async def test_running_executions_cleanup(self):
        engine = _engine()
        engine._get_workflow_definition = AsyncMock(return_value=_workflow())
        execution = _execution()
        engine.running_executions[execution.id] = asyncio.create_task(asyncio.sleep(1))
        await engine._execute_workflow_instance(execution)
        assert execution.id not in engine.running_executions


class TestTemplatesAndVariables:
    async def test_process_variables_substitutes_templates(self):
        engine = _engine()
        wf = _workflow(actions=[
            _action(WorkflowActionType.SEND_DM, {
                "user_id": _param("user_id", "{{trigger.user_id}}"),
                "message": _param("message", "Hi {{trigger.user_name}}"),
            }),
        ])
        execution = _execution(trigger_data={
            "type": "user_joined", "user_id": "U9", "user_name": "Bob"})
        await engine._process_variables(execution, wf, execution.trigger_data)
        dm = wf.actions[0]
        assert dm.parameters["user_id"].value == "U9"
        assert dm.parameters["message"].value == "Hi Bob"

    async def test_substitute_template_nested(self):
        engine = _engine()
        variables = {"trigger": {"user": {"name": "Alice"}}, "missing": None}
        out = await engine._substitute_template(
            "Hello {{trigger.user.name}}, id={{trigger.id}}", variables)
        assert out == "Hello Alice, id="

    async def test_substitute_template_error_returns_original(self):
        engine = _engine()
        with patch("integrations.slack_workflow_engine.re.sub", side_effect=RuntimeError("x")):
            out = await engine._substitute_template("{{a}}", {"a": "1"})
        assert out == "{{a}}"

    def test_get_nested_variable(self):
        engine = _engine()
        data = {"a": {"b": {"c": "deep"}}}
        assert engine._get_nested_variable(data, "a.b.c") == "deep"
        assert engine._get_nested_variable(data, "a.x.y", "dflt") == "dflt"
        assert engine._get_nested_variable(data, "a.b.c.d", "dflt") == "dflt"
        assert engine._get_nested_variable(data, 12345, "dflt") == "dflt"

    def test_should_execute_action_always_true(self):
        engine = _engine()
        assert engine._should_execute_action(_execution(), _action(WorkflowActionType.CREATE_TASK)) is True

    async def test_execute_action_no_handler(self):
        engine = _engine()
        engine.action_handlers = {}
        with pytest.raises(ValueError):
            await engine._execute_action(_execution(), _action(WorkflowActionType.CREATE_TASK))

    async def test_register_action_handler(self):
        engine = _engine()

        async def custom_handler(execution, action):
            return {"custom": True}

        await engine.register_action_handler(WorkflowActionType.CREATE_TASK, custom_handler)
        result = await engine._execute_action(_execution(), _action(WorkflowActionType.CREATE_TASK))
        assert result == {"custom": True}

    async def test_get_workflow_definition_returns_none(self):
        engine = _engine()
        assert await engine._get_workflow_definition("wf-1") is None


class TestActionHandlers:
    async def test_send_dm_api_success(self):
        engine = _engine()
        slack = MagicMock()
        slack.send_dm = AsyncMock(return_value={
            "ok": True, "timestamp": "ts", "message_id": "dm-1"})
        engine.slack_service = slack
        action = _action(WorkflowActionType.SEND_DM, {
            "user_id": _param("user_id", "U1"),
            "message": _param("message", "hello")})
        result = await engine._handle_send_dm(_execution(), action)
        assert result["method"] == "slack_api"
        assert result["message_id"] == "dm-1"

    async def test_send_dm_api_not_ok_falls_back(self):
        engine = _engine()
        slack = MagicMock()
        slack.send_dm = AsyncMock(return_value={"ok": False})
        engine.slack_service = slack
        action = _action(WorkflowActionType.SEND_DM, {
            "user_id": _param("user_id", "U1"),
            "message": _param("message", "hello")})
        result = await engine._handle_send_dm(_execution(), action)
        assert result["method"] == "mock"

    async def test_send_dm_api_error_falls_back(self):
        engine = _engine()
        slack = MagicMock()
        slack.send_dm = AsyncMock(side_effect=RuntimeError("api down"))
        engine.slack_service = slack
        action = _action(WorkflowActionType.SEND_DM, {
            "user_id": _param("user_id", "U1"),
            "message": _param("message", "hello")})
        result = await engine._handle_send_dm(_execution(), action)
        assert result["method"] == "mock"

    async def test_create_channel_api_failure_falls_back(self):
        engine = _engine()
        slack = MagicMock()
        slack.create_channel = AsyncMock(return_value={"ok": False})
        engine.slack_service = slack
        action = _action(WorkflowActionType.CREATE_CHANNEL, {
            "name": _param("name", "new-room"),
            "private": _param("private", True),
            "description": _param("description", "d")})
        result = await engine._handle_create_channel(_execution(), action)
        assert result["method"] == "mock"
        assert result["is_private"] is True

    async def test_create_channel_api_error_falls_back(self):
        engine = _engine()
        slack = MagicMock()
        slack.create_channel = AsyncMock(side_effect=RuntimeError("api down"))
        engine.slack_service = slack
        action = _action(WorkflowActionType.CREATE_CHANNEL, {
            "name": _param("name", "new-room")})
        result = await engine._handle_create_channel(_execution(), action)
        assert result["method"] == "mock"

    async def test_invite_user_api_failure_falls_back(self):
        engine = _engine()
        slack = MagicMock()
        slack.invite_to_channel = AsyncMock(return_value={"ok": False})
        engine.slack_service = slack
        action = _action(WorkflowActionType.INVITE_USER, {
            "channel": _param("channel", "C1"),
            "user_ids": _param("user_ids", ["U1"])})
        result = await engine._handle_invite_user(_execution(), action)
        assert result["method"] == "mock"

    async def test_invite_user_api_error_falls_back(self):
        engine = _engine()
        slack = MagicMock()
        slack.invite_to_channel = AsyncMock(side_effect=RuntimeError("api down"))
        engine.slack_service = slack
        action = _action(WorkflowActionType.INVITE_USER, {
            "channel": _param("channel", "C1"),
            "user_ids": _param("user_ids", "U1")})
        result = await engine._handle_invite_user(_execution(), action)
        assert result["method"] == "mock"
        assert result["invited_users"] == ["U1"]

    async def test_add_reaction_api_failure_falls_back(self):
        engine = _engine()
        slack = MagicMock()
        slack.add_reaction = AsyncMock(return_value={"ok": False})
        engine.slack_service = slack
        action = _action(WorkflowActionType.ADD_REACTION, {
            "channel": _param("channel", "C1"),
            "message_ts": _param("message_ts", "123"),
            "emoji": _param("emoji", "+1")})
        result = await engine._handle_add_reaction(_execution(), action)
        assert result["method"] == "mock"

    async def test_add_reaction_api_error_falls_back(self):
        engine = _engine()
        slack = MagicMock()
        slack.add_reaction = AsyncMock(side_effect=RuntimeError("api down"))
        engine.slack_service = slack
        action = _action(WorkflowActionType.ADD_REACTION, {
            "channel": _param("channel", "C1"),
            "message_ts": _param("message_ts", "123"),
            "emoji": _param("emoji", "+1")})
        result = await engine._handle_add_reaction(_execution(), action)
        assert result["method"] == "mock"

    async def test_pin_message_api_failure_falls_back(self):
        engine = _engine()
        slack = MagicMock()
        slack.pin_message = AsyncMock(return_value={"ok": False})
        engine.slack_service = slack
        action = _action(WorkflowActionType.PIN_MESSAGE, {
            "channel": _param("channel", "C1"),
            "message_ts": _param("message_ts", "123")})
        result = await engine._handle_pin_message(_execution(), action)
        assert result["method"] == "mock"

    async def test_pin_message_api_error_falls_back(self):
        engine = _engine()
        slack = MagicMock()
        slack.pin_message = AsyncMock(side_effect=RuntimeError("api down"))
        engine.slack_service = slack
        action = _action(WorkflowActionType.PIN_MESSAGE, {
            "channel": _param("channel", "C1"),
            "message_ts": _param("message_ts", "123")})
        result = await engine._handle_pin_message(_execution(), action)
        assert result["method"] == "mock"

    async def test_create_task(self):
        engine = _engine()
        action = _action(WorkflowActionType.CREATE_TASK, {
            "title": _param("title", "T"),
            "description": _param("description", "D"),
            "assignee": _param("assignee", "U1")})
        result = await engine._handle_create_task(_execution(), action)
        assert result["title"] == "T"
        assert result["status"] == "open"

    async def test_update_status(self):
        engine = _engine()
        action = _action(WorkflowActionType.UPDATE_STATUS, {
            "status": _param("status", "busy"),
            "emoji": _param("emoji", ":busy:")})
        result = await engine._handle_update_status(_execution(), action)
        assert result["status_text"] == "busy"

    async def test_call_api(self):
        engine = _engine()
        action = _action(WorkflowActionType.CALL_API, {
            "endpoint": _param("endpoint", "/api/x"),
            "method": _param("method", "POST"),
            "headers": _param("headers", {"X": "1"}),
            "data": _param("data", {"a": 1})})
        result = await engine._handle_call_api(_execution(), action)
        assert result["endpoint"] == "/api/x"
        assert result["status_code"] == 200

    async def test_send_email(self):
        engine = _engine()
        action = _action(WorkflowActionType.SEND_EMAIL, {
            "to": _param("to", "a@b.c"),
            "subject": _param("subject", "S"),
            "body": _param("body", "B")})
        result = await engine._handle_send_email(_execution(), action)
        assert result["to"] == "a@b.c"

    async def test_execute_script(self):
        engine = _engine()
        action = _action(WorkflowActionType.EXECUTE_SCRIPT, {
            "script": _param("script", "echo hi"),
            "args": _param("args", ["-x"])})
        result = await engine._handle_execute_script(_execution(), action)
        assert result["exit_code"] == 0

    async def test_update_spreadsheet(self):
        engine = _engine()
        action = _action(WorkflowActionType.UPDATE_SPREADSHEET, {
            "spreadsheet_id": _param("spreadsheet_id", "s1"),
            "range": _param("range", "A1:B2"),
            "values": _param("values", [[1, 2]])})
        result = await engine._handle_update_spreadsheet(_execution(), action)
        assert result["updated_cells"] == 1

    async def test_update_spreadsheet_missing_values(self):
        engine = _engine()
        action = _action(WorkflowActionType.UPDATE_SPREADSHEET, {
            "spreadsheet_id": _param("spreadsheet_id", "s1")})
        result = await engine._handle_update_spreadsheet(_execution(), action)
        assert result["updated_cells"] == 0

    async def test_create_meeting(self):
        engine = _engine()
        action = _action(WorkflowActionType.CREATE_MEETING, {
            "title": _param("title", "Sync"),
            "attendees": _param("attendees", ["U1"]),
            "start_time": _param("start_time", "2026-08-10T10:00"),
            "duration": _param("duration", 30)})
        result = await engine._handle_create_meeting(_execution(), action)
        assert result["title"] == "Sync"

    async def test_unknown_action_raises(self):
        engine = _engine()
        with pytest.raises(ValueError):
            await engine._handle_unknown_action(_execution(), _action(WorkflowActionType.CREATE_TASK))


class TestExecutionManagement:
    def test_log_execution_and_truncation(self):
        engine = _engine()
        execution = _execution()
        engine._log_execution(execution, "info", "starting")
        engine._log_execution(execution, "error", "boom")
        assert execution.logs[0]["level"] == "info"
        assert execution.logs[1]["level"] == "error"
        assert "boom" in execution.logs[1]["message"]
        execution.logs = [{"l": i} for i in range(120)]
        engine._log_execution(execution, "info", "again")
        assert len(execution.logs) <= 100

    def test_update_execution_stats(self):
        engine = _engine()
        start = datetime.now(timezone.utc)
        completed = WorkflowExecution(
            id="e1", workflow_id="w", trigger_type=WorkflowTriggerType.MESSAGE,
            trigger_data={}, status=WorkflowExecutionStatus.COMPLETED,
            priority=WorkflowExecutionPriority.NORMAL, started_at=start,
            completed_at=start + timedelta(seconds=5))
        engine._update_execution_stats(completed)
        failed = WorkflowExecution(
            id="e2", workflow_id="w", trigger_type=WorkflowTriggerType.MESSAGE,
            trigger_data={}, status=WorkflowExecutionStatus.FAILED,
            priority=WorkflowExecutionPriority.NORMAL, started_at=start,
            completed_at=start + timedelta(seconds=10))
        engine._update_execution_stats(failed)
        stats = engine.get_execution_stats()
        assert stats["total_executions"] == 2
        assert stats["successful_executions"] == 1
        assert stats["failed_executions"] == 1
        assert stats["average_execution_time"] == 7.5

    async def test_get_execution_status_running(self):
        engine = _engine()
        task = asyncio.create_task(asyncio.sleep(1))
        engine.running_executions["exec-live"] = task
        status = engine.get_execution_status("exec-live")
        assert status.status == WorkflowExecutionStatus.RUNNING
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    def test_get_execution_status_from_history(self):
        engine = _engine()
        execution = _execution()
        engine.execution_history.append(execution)
        assert engine.get_execution_status(execution.id) is execution
        assert engine.get_execution_status("nope") is None

    def test_get_workflow_executions_sorted_and_limited(self):
        engine = _engine()
        now = datetime.now(timezone.utc)
        old = _execution(id="old", workflow_id="wf-1", started_at=now - timedelta(hours=1))
        new = _execution(id="new", workflow_id="wf-1", started_at=now)
        other = _execution(id="other", workflow_id="wf-2", started_at=now)
        engine.execution_history.extend([old, new, other])
        results = engine.get_workflow_executions("wf-1", limit=10)
        assert [r.id for r in results] == ["new", "old"]
        results = engine.get_workflow_executions("wf-1", limit=1)
        assert [r.id for r in results] == ["new"]

    async def test_cancel_execution(self):
        engine = _engine()
        assert engine.cancel_execution("exec-gone") is False
        task = asyncio.create_task(asyncio.sleep(10))
        engine.running_executions["exec-live"] = task
        assert engine.cancel_execution("exec-live") is True
        assert "exec-live" not in engine.running_executions
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def test_cleanup(self):
        engine = _engine()
        engine.running_executions["exec-live"] = asyncio.create_task(asyncio.sleep(10))
        await engine.cleanup()
        assert not engine.running_executions
