"""Regression coverage for explicitly uncertain workflow effects.

The tests import the real workflow engine and the real Outlook connector.
Only external boundaries are replaced with in-memory fakes: the state store,
websocket notifications, the database session and the Outlook HTTP call.
No live provider or database call is made.
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import core.workflow_engine as workflow_engine  # noqa: E402
from core.workflow_engine import UncertainEffectError, WorkflowEngine  # noqa: E402
from integrations.outlook_service import OutlookService  # noqa: E402


UNKNOWN_FORWARD = {
    "status": "unknown",
    "outcome": "unknown_effect",
    "provider_accepted": False,
    "effect_uncertain": True,
    "message_id": "message-1",
    "reason": "transport_error",
    "http_status": None,
}
ACCEPTED_FORWARD = {
    "status": "provider_accepted",
    "outcome": "provider_accepted",
    "provider_accepted": True,
    "effect_uncertain": False,
    "message_id": "message-1",
    "http_status": 202,
}
REJECTED_FORWARD = {
    "status": "not_forwarded",
    "outcome": "not_forwarded",
    "provider_accepted": False,
    "effect_uncertain": False,
    "message_id": "message-1",
    "reason": "provider_rejected",
    "http_status": 403,
}


class _FakeStateManager:
    """In-memory replacement for the durable execution store."""

    def __init__(self, state=None):
        self.state = state if state is not None else {
            "status": "PENDING",
            "input_data": {},
            "steps": {},
            "outputs": {},
            "step_results": {},
            "error": None,
        }
        self.step_updates = []
        self.execution_updates = []
        self.input_updates = []

    async def get_execution_state(self, _execution_id):
        return self.state

    async def update_step_status(
        self,
        _execution_id,
        step_id,
        status,
        output=None,
        error=None,
    ):
        entry = self.state["steps"].setdefault(step_id, {})
        entry["status"] = status
        if output is not None:
            entry["output"] = output
        if error is not None:
            entry["error"] = error
        self.step_updates.append((step_id, status))
        return True

    async def update_execution_status(
        self,
        _execution_id,
        status,
        error=None,
    ):
        self.state["status"] = status
        if error is not None:
            self.state["error"] = error
        self.execution_updates.append((status, error))
        return True

    async def update_execution_inputs(self, _execution_id, inputs):
        self.state.setdefault("input_data", {}).update(inputs)
        self.input_updates.append(dict(inputs))
        return True


class _WebsocketManager:
    def __init__(self):
        self.events = []

    async def notify_workflow_status(self, *args, **kwargs):
        self.events.append((args, kwargs))


class _NoopNotifier:
    async def notify_paused(self, **_kwargs):
        return None

    async def notify_failure(self, **_kwargs):
        return None

    async def notify_completion(self, **_kwargs):
        return None


def _db_disabled(*_args, **_kwargs):
    raise RuntimeError("database boundary disabled in test")


@pytest.fixture
def boundaries(monkeypatch):
    ws_manager = _WebsocketManager()
    monkeypatch.setattr(
        workflow_engine, "get_connection_manager", lambda: ws_manager)
    monkeypatch.setattr(workflow_engine, "notifier", _NoopNotifier())
    monkeypatch.setattr(workflow_engine, "get_db_session", _db_disabled)
    return ws_manager


def _build_engine(state_manager):
    engine = WorkflowEngine()
    engine.state_manager = state_manager
    # Task admission is a policy/database boundary; this packet exercises the
    # step dispatch and resume behavior itself.
    engine._admit_never_autonomous_task = AsyncMock(return_value=None)
    return engine


def _install_forward(monkeypatch, result):
    calls = []

    async def _forward_email(self, **kwargs):
        calls.append(kwargs)
        return dict(result)

    monkeypatch.setattr(OutlookService, "forward_email", _forward_email)
    return calls


def _install_slow_forward(monkeypatch, delay=0.2):
    """Keep a real provider call in flight past the engine's short deadline."""
    calls = []

    async def _forward_email(self, **kwargs):
        calls.append(kwargs)
        await asyncio.sleep(delay)
        return dict(ACCEPTED_FORWARD)

    monkeypatch.setattr(OutlookService, "forward_email", _forward_email)
    return calls


def _forward_step(fallback_service=None, timeout=None):
    step = {
        "id": "forward-1",
        "service": "outlook",
        "action": "forward_email",
        "parameters": {},
    }
    if fallback_service:
        step["fallback_service"] = fallback_service
    if timeout is not None:
        step["timeout"] = timeout
    return step


def _forward_params():
    return {
        "user_id": "user-1",
        "message_id": "message-1",
        "to_recipients": ["recipient@example.com"],
    }


def test_uncertain_forward_is_not_retried_and_never_falls_back(
    boundaries, monkeypatch
):
    calls = _install_forward(monkeypatch, UNKNOWN_FORWARD)
    fallback = AsyncMock()

    async def _run():
        engine = _build_engine(_FakeStateManager())
        monkeypatch.setattr(engine, "_execute_email_action", fallback)
        with pytest.raises(UncertainEffectError) as raised:
            await engine._execute_step(
                _forward_step(fallback_service="email"),
                _forward_params(),
            )
        return raised.value

    error = asyncio.run(_run())
    assert len(calls) == 1  # no automatic retry
    assert fallback.await_count == 0  # no fallback after a possible effect
    assert error.retryable is False
    assert error.evidence["status"] == "unknown"
    assert error.evidence["provider_accepted"] is False
    assert error.evidence["reason"] == "transport_error"


def test_primary_deadline_during_forward_is_uncertain_without_retry_or_fallback(
    boundaries, monkeypatch
):
    calls = _install_slow_forward(monkeypatch)
    fallback = AsyncMock()

    async def _run():
        engine = _build_engine(_FakeStateManager())
        monkeypatch.setattr(engine, "_execute_email_action", fallback)
        with pytest.raises(UncertainEffectError) as raised:
            await engine._execute_step(
                _forward_step(fallback_service="email", timeout=0.01),
                _forward_params(),
            )
        return raised.value

    error = asyncio.run(_run())
    assert len(calls) == 1  # the real retry decorator did not repeat it
    assert fallback.await_count == 0  # a possibly-started effect never falls back
    assert error.retryable is False
    assert error.evidence["effect_uncertain"] is True
    assert error.evidence["outcome"] == "unknown_effect"
    assert error.evidence["reason"] == "workflow_deadline"
    assert "workflow_deadline" in str(error)


def test_fallback_deadline_during_forward_is_uncertain_without_retry(
    boundaries, monkeypatch
):
    calls = _install_slow_forward(monkeypatch)
    primary = AsyncMock(side_effect=RuntimeError("primary unavailable"))
    step = _forward_step(fallback_service="outlook", timeout=0.01)
    step["service"] = "slack"

    async def _run():
        engine = _build_engine(_FakeStateManager())
        monkeypatch.setattr(engine, "_execute_slack_action", primary)
        with pytest.raises(UncertainEffectError) as raised:
            await engine._execute_step(step, _forward_params())
        return raised.value

    error = asyncio.run(_run())
    assert primary.await_count == 1
    assert len(calls) == 1  # fallback dispatch timed out once, with no retry
    assert error.retryable is False
    assert error.evidence["effect_uncertain"] is True
    assert error.evidence["reason"] == "workflow_deadline"


def test_deadline_policy_keeps_other_timeouts_and_model_subtype():
    read_error = workflow_engine._deadline_step_error(
        "outlook", "get_emails", "read-1", 0.01)
    model_error = workflow_engine._deadline_step_error(
        "ai", "generate_content", "model-1", 0.01)

    assert isinstance(read_error, workflow_engine.StepTimeoutError)
    assert not isinstance(read_error, workflow_engine.ModelStepTimeoutError)
    assert read_error.retryable is True
    assert isinstance(model_error, workflow_engine.ModelStepTimeoutError)
    assert model_error.retryable is False


def test_accepted_forward_is_provider_acceptance_only(boundaries, monkeypatch):
    calls = _install_forward(monkeypatch, ACCEPTED_FORWARD)

    async def _run():
        engine = _build_engine(_FakeStateManager())
        return await engine._execute_step(
            _forward_step(), _forward_params())

    result = asyncio.run(_run())
    assert len(calls) == 1
    assert result["status"] == "success"
    assert result["result"]["provider_accepted"] is True
    assert result["result"]["outcome"] == "provider_accepted"
    assert result["result"]["effect_uncertain"] is False
    assert result["result"]["result"]["provider_accepted"] is True


def test_rejected_forward_is_a_failure_not_uncertainty(
    boundaries, monkeypatch
):
    _install_forward(monkeypatch, REJECTED_FORWARD)

    async def _run():
        engine = _build_engine(_FakeStateManager())
        with pytest.raises(Exception) as raised:
            await engine._execute_step(_forward_step(), _forward_params())
        return raised.value

    error = asyncio.run(_run())
    assert not isinstance(error, UncertainEffectError)
    assert "rejected" in str(error).lower()


def test_linear_uncertainty_pauses_before_downstream_step(
    boundaries, monkeypatch
):
    calls = _install_forward(monkeypatch, UNKNOWN_FORWARD)

    async def _run():
        engine = _build_engine(_FakeStateManager())
        workflow = {
            "id": "workflow-linear",
            "name": "Linear uncertainty",
            "steps": [
                {
                    "id": "step-1",
                    "service": "outlook",
                    "action": "forward_email",
                    "parameters": {},
                    "sequence_order": 1,
                },
                {
                    "id": "step-2",
                    "service": "email",
                    "action": "send_email",
                    "parameters": {},
                    "sequence_order": 2,
                },
            ],
        }
        await engine._run_execution_body("execution-linear", workflow)
        return engine, engine.state_manager

    engine, state = asyncio.run(_run())
    assert len(calls) == 1
    assert state.state["status"] == "PAUSED"
    assert state.state["steps"]["step-1"]["status"] == "PAUSED"
    assert state.state["steps"]["step-1"]["output"]["effect_uncertain"] is True
    assert state.state["steps"]["step-1"]["output"]["provider_accepted"] is False
    assert state.state["steps"].get("step-2", {}).get("status") != "COMPLETED"


def test_linear_deadline_in_forward_pauses_before_downstream_step(
    boundaries, monkeypatch
):
    calls = _install_slow_forward(monkeypatch)

    async def _run():
        engine = _build_engine(_FakeStateManager())
        workflow = {
            "id": "workflow-linear-deadline",
            "name": "Linear deadline",
            "steps": [
                {
                    "id": "step-1",
                    "service": "outlook",
                    "action": "forward_email",
                    "parameters": {},
                    "sequence_order": 1,
                    "timeout": 0.01,
                },
                {
                    "id": "step-2",
                    "service": "email",
                    "action": "send_email",
                    "parameters": {},
                    "sequence_order": 2,
                },
            ],
        }
        await engine._run_execution_body("execution-linear-deadline", workflow)
        return engine, engine.state_manager

    engine, state = asyncio.run(_run())
    assert len(calls) == 1
    assert state.state["status"] == "PAUSED"
    assert state.state["steps"]["step-1"]["status"] == "PAUSED"
    uncertainty = state.state["steps"]["step-1"]["output"]
    assert uncertainty["effect_uncertain"] is True
    assert uncertainty["action_reason"] == "workflow_deadline"
    assert state.state["steps"].get("step-2", {}).get("status") != "COMPLETED"


def test_graph_uncertainty_pauses_before_downstream_node(
    boundaries, monkeypatch
):
    calls = _install_forward(monkeypatch, UNKNOWN_FORWARD)

    async def _run():
        engine = _build_engine(_FakeStateManager())
        workflow = {
            "id": "workflow-graph",
            "name": "Graph uncertainty",
            "nodes": [
                {
                    "id": "node-1",
                    "title": "Forward",
                    "type": "action",
                    "config": {
                        "service": "outlook",
                        "action": "forward_email",
                        "parameters": {},
                    },
                },
                {
                    "id": "node-2",
                    "title": "Downstream",
                    "type": "action",
                    "config": {
                        "service": "email",
                        "action": "send_email",
                        "parameters": {},
                    },
                },
            ],
            "connections": [
                {
                    "source": "node-1",
                    "target": "node-2",
                    "condition": "True",
                },
            ],
        }
        await engine._execute_workflow_graph(
            "execution-graph",
            workflow,
            engine.state_manager.state,
            boundaries,
            "user-1",
            datetime.now(timezone.utc),
        )
        return engine, engine.state_manager

    engine, state = asyncio.run(_run())
    assert len(calls) == 1
    assert state.state["status"] == "PAUSED"
    assert state.state["steps"]["node-1"]["status"] == "PAUSED"
    assert state.state["steps"]["node-1"]["output"]["effect_uncertain"] is True
    assert state.state["steps"].get("node-2", {}).get("status") != "COMPLETED"


def test_resume_refuses_uncertain_paused_step_before_any_mutation(boundaries):
    state = {
        "status": "PAUSED",
        "input_data": {"existing": "value"},
        "steps": {
            "forward-1": {
                "status": "PAUSED",
                "output": {
                    "effect_uncertain": True,
                    "reason": "effect_uncertain",
                    "outcome": "unknown_effect",
                },
            },
        },
        "outputs": {},
        "step_results": {},
        "error": "uncertain outcome",
    }
    state_manager = _FakeStateManager(state)

    async def _run():
        engine = _build_engine(state_manager)
        engine._run_execution = AsyncMock()
        resumed = await engine.resume_workflow(
            "execution-uncertain",
            {"id": "workflow-uncertain"},
            {
                # A caller cannot override an uncertain persisted outcome.
                "approved": True,
                "override": True,
                "allow_uncertain_resume": True,
                "effect_uncertain": False,
            },
        )
        return resumed, engine

    resumed, engine = asyncio.run(_run())
    assert resumed is False
    assert state_manager.input_updates == []
    assert state_manager.execution_updates == []
    assert state_manager.step_updates == []
    assert engine._run_execution.await_count == 0
    assert state_manager.state["status"] == "PAUSED"
    assert state_manager.state["input_data"] == {"existing": "value"}


def test_ordinary_paused_resume_updates_inputs_and_dispatches(boundaries):
    state = {
        "status": "PAUSED",
        "input_data": {},
        "steps": {
            "step-1": {
                "status": "PAUSED",
                "error": "Missing input: customer",
            },
        },
        "outputs": {},
        "step_results": {},
        "error": "Missing input: customer",
    }
    state_manager = _FakeStateManager(state)

    async def _run():
        engine = _build_engine(state_manager)
        engine._run_execution = AsyncMock()
        resumed = await engine.resume_workflow(
            "execution-normal",
            {"id": "workflow-normal"},
            {"customer": "acme"},
        )
        await asyncio.gather(*engine._background_tasks)
        return resumed, engine

    resumed, engine = asyncio.run(_run())
    assert resumed is True
    assert state_manager.input_updates == [{"customer": "acme"}]
    assert state_manager.state["input_data"]["customer"] == "acme"
    assert ("RUNNING", None) in state_manager.execution_updates
    assert state_manager.state["status"] == "RUNNING"
    assert engine._run_execution.await_count == 1
