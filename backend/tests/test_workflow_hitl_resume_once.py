"""WF-05 — policy denial pauses durably; an authorized approval resumes the
same workflow and the critical step executes exactly once.

The engine used to re-run the governance check on resume without consuming
the HITL decision, so an approved workflow paused again forever. The fix
re-reads the persisted HITL row and binds it to execution + step + action,
consuming it before dispatch.
"""
from __future__ import annotations

import contextlib
import os

os.environ.setdefault("TESTING", "1")

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, MagicMock, patch

from core.models import AgentRegistry, Base, HITLAction
from core.workflow_engine import WorkflowEngine


class FakeStateManager:
    """In-memory execution state with the real async contract."""

    def __init__(self, state):
        self.state = state

    async def get_execution_state(self, execution_id):
        import copy

        return copy.deepcopy(self.state)

    async def update_execution_status(self, execution_id, status, error=None):
        self.state["status"] = status
        if error is not None:
            self.state["error"] = error

    async def update_step_status(self, execution_id, step_id, status,
                                 output=None, error=None):
        step = self.state.setdefault("steps", {}).setdefault(step_id, {})
        step["status"] = status
        if output is not None:
            step["output"] = output
            self.state.setdefault("outputs", {})[step_id] = output
        if error is not None:
            step["error"] = error

    async def update_execution_inputs(self, execution_id, new_inputs):
        self.state.setdefault("input_data", {}).update(new_inputs)

    async def create_execution(self, workflow_id, input_data):
        return "ex-1"


@pytest.fixture()
def world(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/wf05.db")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextlib.contextmanager
    def session():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    with session() as db:
        db.add(AgentRegistry(
            id="ag-1", name="Student", category="test",
            module_path="tests.agent", class_name="Agent", status="student",
            workspace_id="default",
        ))
        db.commit()
    yield {"session": session}
    engine.dispose()


def _approved_action(db, *, execution_id="ex-1", step_id="s1",
                     action_type="send_email", status="approved"):
    db.add(HITLAction(
        id="hitl-1", action_type=action_type, platform="workflow",
        params={"execution_id": execution_id, "workflow_id": "wf-1",
                "step_id": step_id, "parameters": {"to": "x"}},
        status=status, workspace_id="default", tenant_id="default",
        created_at=datetime.now(),
    ))
    db.commit()


def _step():
    return {
        "id": "s1", "type": "action", "action": "send_email",
        "parameters": {"to": "x@example.invalid"},
        "sequence_order": 0,
    }


def _run(engine, state, world, monkeypatch):
    sm = FakeStateManager(state)
    engine.state_manager = sm
    ws = MagicMock()
    ws.notify_workflow_status = AsyncMock()
    analytics = MagicMock()
    governance = MagicMock()
    governance.can_perform_action_async = AsyncMock(
        return_value={"allowed": False, "reason": "maturity too low"})
    governance.request_approval = MagicMock(return_value="hitl-new")
    executed = AsyncMock(return_value={"status": "success", "result": {}})

    @contextlib.contextmanager
    def db_session():
        with world["session"]() as db:
            yield db

    import asyncio

    with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
         patch("core.workflow_engine.get_db_session", db_session), \
         patch("core.analytics_engine.get_analytics_engine",
               return_value=analytics), \
         patch("core.service_factory.ServiceFactory.get_governance_service",
               return_value=governance), \
         patch.object(engine, "_execute_step", new=executed), \
         patch("core.workflow_notifier.notifier.notify_completion",
               new=AsyncMock()):
        asyncio.run(engine._run_execution("ex-1", {
            "id": "wf-1", "agent_id": "ag-1", "tenant_id": "default",
            "steps": [_step()],
        }))
    return sm, executed, governance


def test_denial_pauses_without_executing_and_files_exact_effect(world):
    engine = WorkflowEngine()
    state = {"status": "RUNNING", "steps": {}, "input_data": {},
             "outputs": {}}
    sm, executed, governance = _run(engine, state, world, None)

    executed.assert_not_called()
    assert sm.state["status"] == "PAUSED"
    assert sm.state["steps"]["s1"]["status"] == "PAUSED"
    governance.request_approval.assert_called_once()
    params = governance.request_approval.call_args.kwargs["params"]
    assert params["execution_id"] == "ex-1"
    assert params["step_id"] == "s1"


def test_durable_approval_resumes_same_workflow_once(world):
    with world["session"]() as db:
        _approved_action(db)
    engine = WorkflowEngine()
    state = {
        "status": "PAUSED",
        "steps": {"s1": {"status": "PAUSED"}},
        "input_data": {"approved": True, "hitl_action_id": "hitl-1"},
        "outputs": {},
    }
    sm, executed, governance = _run(engine, state, world, None)

    assert executed.await_count == 1, "the critical step must run after approval"
    assert sm.state["steps"]["s1"]["status"] == "COMPLETED"
    assert "hitl-1" in sm.state["input_data"]["consumed_hitl_action_ids"]
    governance.request_approval.assert_not_called()

    # A second resume finds the step COMPLETED and must not execute again.
    _run(engine, sm.state, world, None)
    assert executed.await_count == 1, "completed critical step must not rerun"


def test_approval_for_a_different_step_or_execution_cannot_unlock(world):
    with world["session"]() as db:
        _approved_action(db, step_id="other-step")
    engine = WorkflowEngine()
    state = {
        "status": "PAUSED",
        "steps": {"s1": {"status": "PAUSED"}},
        "input_data": {"approved": True, "hitl_action_id": "hitl-1"},
        "outputs": {},
    }
    sm, executed, governance = _run(engine, state, world, None)
    executed.assert_not_called()
    assert sm.state["steps"]["s1"]["status"] == "PAUSED"
    governance.request_approval.assert_called_once()


def test_rejected_or_missing_hitl_row_cannot_unlock(world):
    with world["session"]() as db:
        _approved_action(db, status="rejected")
    engine = WorkflowEngine()
    state = {
        "status": "PAUSED",
        "steps": {"s1": {"status": "PAUSED"}},
        "input_data": {"approved": True, "hitl_action_id": "hitl-1"},
        "outputs": {},
    }
    sm, executed, governance = _run(engine, state, world, None)
    executed.assert_not_called()
    assert sm.state["steps"]["s1"]["status"] == "PAUSED"


def test_crash_after_dispatch_does_not_resend_approved_step(world):
    """A step left RUNNING after dispatch is uncertain, never resent."""
    with world["session"]() as db:
        _approved_action(db)
    engine = WorkflowEngine()
    state = {
        "status": "PAUSED",
        "steps": {"s1": {"status": "RUNNING"}},
        "input_data": {"approved": True, "hitl_action_id": "hitl-1"},
        "outputs": {},
    }
    sm, executed, governance = _run(engine, state, world, None)
    executed.assert_not_called()
    assert sm.state["steps"]["s1"]["status"] == "PAUSED"
    assert "uncertain" in (sm.state["steps"]["s1"].get("error") or "").lower()
    assert sm.state["status"] == "PAUSED"
