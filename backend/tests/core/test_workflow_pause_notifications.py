"""
Tests for workflow pause notifications (HITL).

Covers:
- Missing-input pause fans out a pause notification (notifier + in-app + EventBus)
- Governance/trust denial pauses the workflow (not FAILED) and creates a HITL action
- WorkflowNotifier.notify_paused honors notification settings
- resume_workflow publishes WORKFLOW_RESUMED
"""
import asyncio
import uuid
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.workflow_engine import WorkflowEngine
from core.workflow_notifier import NotificationSettings, WorkflowNotifier


class FakeStateManager:
    """In-memory stand-in for ExecutionStateManager (no shared sqlite)."""

    def __init__(self) -> None:
        self.executions: dict = {}

    async def create_execution(self, workflow_id: str, input_data: dict) -> str:
        execution_id = str(uuid.uuid4())
        self.executions[execution_id] = {
            "execution_id": execution_id,
            "workflow_id": workflow_id,
            "status": "PENDING",
            "input_data": dict(input_data),
            "steps": {},
            "outputs": {},
            "context": {},
        }
        return execution_id

    async def update_step_status(self, execution_id, step_id, status, output=None, error=None):
        state = self.executions[execution_id]
        step = state["steps"].setdefault(step_id, {"id": step_id})
        step["status"] = status
        if output is not None:
            step["output"] = output
            state["outputs"][step_id] = output
        if error is not None:
            step["error"] = error

    async def update_execution_status(self, execution_id, status, error=None):
        state = self.executions[execution_id]
        state["status"] = status
        if error is not None:
            state["error"] = error

    async def update_execution_inputs(self, execution_id, new_inputs):
        self.executions[execution_id]["input_data"].update(new_inputs)

    async def get_execution_state(self, execution_id):
        return self.executions.get(execution_id)


async def wait_for_background_tasks(engine: WorkflowEngine, timeout: float = 10.0) -> bool:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if all(t.done() for t in engine._background_tasks):
            return True
        await asyncio.sleep(0.05)
    return False


@contextmanager
def _fake_db_session(agent_record=..., step_exec_query=None):
    """Yield a MagicMock db whose AgentRegistry lookup returns agent_record."""
    db = MagicMock()
    agent_result = MagicMock()
    agent_result.first.return_value = None if agent_record is ... else agent_record
    log_result = MagicMock()
    log_result.first.return_value = None
    db.query.side_effect = lambda model: agent_result if model.__name__ == "AgentRegistry" else log_result
    yield db


def _linear_workflow() -> dict:
    return {
        "id": "wf-pause-test",
        "name": "Pause Notification Workflow",
        "created_by": "test-user",
        "steps": [
            {
                "id": "step1",
                "name": "Needs Input",
                "sequence_order": 1,
                "service": "default",
                "action": "default",
                "parameters": {"value": "${missing.var}"},
            }
        ],
    }


class TestMissingInputPauseNotifications:
    @pytest.mark.asyncio
    async def test_missing_input_pause_fires_notify_paused(self):
        engine = WorkflowEngine()
        engine.state_manager = FakeStateManager()

        notifier_mock = AsyncMock()
        ws_mock = AsyncMock()
        with patch("core.workflow_engine.notifier", notifier_mock), \
             patch("core.workflow_engine.get_connection_manager", return_value=ws_mock):
            execution_id = await engine.start_workflow(_linear_workflow(), {})
            assert await wait_for_background_tasks(engine)
            await asyncio.sleep(0.1)  # let create_task notification fan-out run

        state = engine.state_manager.executions[execution_id]
        assert state["status"] == "PAUSED"

        notifier_mock.notify_paused.assert_awaited_once()
        kwargs = notifier_mock.notify_paused.await_args.kwargs
        assert kwargs["workflow_id"] == "wf-pause-test"
        assert kwargs["execution_id"] == execution_id
        assert kwargs["missing_var"] == "missing.var"
        assert kwargs["reason"].startswith("Missing input")

    @pytest.mark.asyncio
    async def test_missing_input_pause_sends_in_app_notification(self):
        engine = WorkflowEngine()
        engine.state_manager = FakeStateManager()

        send_mock = AsyncMock(return_value={"success": True})
        ws_mock = AsyncMock()
        with patch("core.workflow_engine.notifier", AsyncMock()), \
             patch("core.workflow_engine.get_connection_manager", return_value=ws_mock), \
             patch("core.notification_service.NotificationService.send_notification", send_mock):
            execution_id = await engine.start_workflow(_linear_workflow(), {})
            assert await wait_for_background_tasks(engine)
            await asyncio.sleep(0.1)

        send_mock.assert_awaited_once()
        user_id, notif_type, data = send_mock.await_args.args
        assert user_id == "test-user"
        assert notif_type == "workflow_paused"
        assert data["action_url"] == f"/workflows/executions/{execution_id}"


class TestGovernancePauseForHitl:
    @pytest.mark.asyncio
    async def test_governance_denial_pauses_and_creates_hitl_action(self):
        """A trust-policy denial must pause for HITL review, not fail."""
        engine = WorkflowEngine()
        engine.state_manager = FakeStateManager()

        governance = MagicMock()
        governance.can_perform_action_async = AsyncMock(
            return_value={"allowed": False, "reason": "Agent maturity below threshold"}
        )
        governance.request_approval = MagicMock(return_value="hitl-action-123")

        agent_record = MagicMock()  # non-None so governance applies
        notifier_mock = AsyncMock()
        ws_mock = AsyncMock()

        workflow = {
            "id": "wf-gov-pause",
            "name": "Governed Workflow",
            "created_by": "test-user",
            "agent_id": "agent-immature",
            "steps": [
                {
                    "id": "step1",
                    "name": "Governed Step",
                    "sequence_order": 1,
                    "service": "default",
                    "action": "send_email",
                    "parameters": {"to": "a@b.com"},
                }
            ],
        }

        with patch("core.workflow_engine.notifier", notifier_mock), \
             patch("core.workflow_engine.get_connection_manager", return_value=ws_mock), \
             patch("core.workflow_engine.get_db_session", _fake_db_session), \
             patch("core.workflow_engine.ServiceFactory.get_governance_service", return_value=governance):
            execution_id = await engine.start_workflow(workflow, {})
            assert await wait_for_background_tasks(engine)
            await asyncio.sleep(0.1)

        state = engine.state_manager.executions[execution_id]
        assert state["status"] == "PAUSED"
        assert "Governance approval required" in state["error"]
        assert state["steps"]["step1"]["status"] == "PAUSED"

        governance.request_approval.assert_called_once()
        req_kwargs = governance.request_approval.call_args.kwargs
        assert req_kwargs["agent_id"] == "agent-immature"
        assert req_kwargs["action_type"] == "send_email"
        assert req_kwargs["params"]["execution_id"] == execution_id

        notifier_mock.notify_paused.assert_awaited_once()
        kwargs = notifier_mock.notify_paused.await_args.kwargs
        assert kwargs["hitl_action_id"] == "hitl-action-123"
        assert "Agent maturity below threshold" in kwargs["reason"]

        # WebSocket must report PAUSED with the HITL reference, not FAILED
        paused_updates = [
            c for c in ws_mock.notify_workflow_status.await_args_list
            if c.args[2] == "PAUSED"
        ]
        assert paused_updates, "expected a PAUSED websocket status"
        assert paused_updates[0].args[3].get("reason") == "hitl_required"

    @pytest.mark.asyncio
    async def test_governance_allowed_proceeds_without_hitl(self):
        engine = WorkflowEngine()
        engine.state_manager = FakeStateManager()

        governance = MagicMock()
        governance.can_perform_action_async = AsyncMock(return_value={"allowed": True})
        governance.request_approval = MagicMock()

        output = {"status": "ok", "result": {"id": "r1"}}
        ws_mock = AsyncMock()
        workflow = {
            "id": "wf-gov-ok",
            "created_by": "test-user",
            "agent_id": "agent-trusted",
            "steps": [
                {
                    "id": "step1",
                    "sequence_order": 1,
                    "action": "default",
                    "parameters": {},
                }
            ],
        }

        with patch("core.workflow_engine.notifier", AsyncMock()), \
             patch("core.workflow_engine.get_connection_manager", return_value=ws_mock), \
             patch("core.workflow_engine.get_db_session", _fake_db_session), \
             patch("core.workflow_engine.ServiceFactory.get_governance_service", return_value=governance), \
             patch.object(engine, "_execute_step", AsyncMock(return_value=output)):
            await engine.start_workflow(workflow, {})
            assert await wait_for_background_tasks(engine)

        state = list(engine.state_manager.executions.values())[0]
        assert state["status"] == "COMPLETED"
        governance.request_approval.assert_not_called()


class TestResumePublishesEvent:
    @pytest.mark.asyncio
    async def test_resume_workflow_publishes_resumed_event(self):
        engine = WorkflowEngine()
        engine.state_manager = FakeStateManager()
        execution_id = await engine.state_manager.create_execution("wf-x", {})
        await engine.state_manager.update_execution_status(execution_id, "PAUSED")

        with patch.object(engine, "_run_execution", AsyncMock()) as run_mock, \
             patch.object(engine, "_publish_orchestration_event") as publish:
            resumed = await engine.resume_workflow(execution_id, {"id": "wf-x"}, {"missing.var": "value"})

        assert resumed is True
        publish.assert_called_once()
        assert publish.call_args.args[0] == "WORKFLOW_RESUMED"
        run_mock.assert_called_once()


class TestWorkflowNotifierPaused:
    @pytest.mark.asyncio
    async def test_notify_paused_sends_slack_when_enabled(self):
        n = WorkflowNotifier()
        n._send_slack = AsyncMock()
        n._send_email = AsyncMock()
        settings = NotificationSettings(slack_enabled=True, email_enabled=False)

        await n.notify_paused(
            workflow_id="wf-1",
            workflow_name="My Workflow",
            execution_id="exec-1",
            reason="Governance approval required",
            step_id="step2",
            hitl_action_id="hitl-1",
            settings=settings,
        )
        n._send_slack.assert_awaited_once()
        n._send_email.assert_not_awaited()
        message = n._send_slack.await_args.args[1]
        assert "Paused" in message
        assert "hitl-1" in message

    @pytest.mark.asyncio
    async def test_notify_paused_skips_when_disabled(self):
        n = WorkflowNotifier()
        n._send_slack = AsyncMock()
        settings = NotificationSettings(enabled=False)

        await n.notify_paused(
            workflow_id="wf-1", workflow_name="w", execution_id="e", reason="r",
            settings=settings,
        )
        n._send_slack.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_notify_paused_disabled_via_pause_flag(self):
        n = WorkflowNotifier()
        n._send_slack = AsyncMock()
        settings = NotificationSettings(notify_on_pause=False)

        await n.notify_paused(
            workflow_id="wf-1", workflow_name="w", execution_id="e", reason="r",
            settings=settings,
        )
        n._send_slack.assert_not_awaited()
