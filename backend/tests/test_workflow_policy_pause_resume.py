"""WF-05: policy denial -> durable pause -> approval -> resume once.

The approval is the persisted HITL row, re-read on resume; the boolean in the
execution inputs cannot authorize anything by itself. A second resume with the
same consumed approval must not execute the step again.
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from core import workflow_engine as workflow_engine_module
from core.database import Base
from core.models import AgentRegistry, HITLAction
from core.workflow_engine import WorkflowEngine


def _step():
    return {
        "id": "s1", "name": "Send decision", "service": "email",
        "action": "send", "parameters": {}, "continue_on_error": False,
        "timeout": None, "input_schema": {}, "output_schema": {},
    }


@pytest.fixture()
def scratch(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'hitl.db'}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    yield Session
    engine.dispose()


def _engine():
    sm = MagicMock()
    state = {"steps": {}, "input_data": {}, "outputs": {}, "status": "RUNNING"}
    sm.get_execution_state = AsyncMock(side_effect=lambda *a, **k: state)
    sm.update_step_status = AsyncMock()
    sm.update_execution_status = AsyncMock()

    def _merge(_execution_id, inputs):
        state["input_data"].update(inputs or {})

    sm.update_execution_inputs = AsyncMock(side_effect=_merge)
    with patch("core.workflow_engine.get_state_manager", return_value=sm):
        engine = WorkflowEngine()
    engine.state_manager = sm
    return engine, state


@pytest.mark.asyncio
async def test_denied_step_pauses_then_resumes_once_after_approval(scratch, tmp_path):
    engine, state = _engine()
    session_db = scratch()
    try:
        session_db.add(AgentRegistry(
            id="ag-1", name="ag-1", category="test",
            module_path="test.module", class_name="TestAgent",
            tenant_id="tenant-1", workspace_id="ws-1"))
        session_db.add(HITLAction(
            id="hitl-1", tenant_id="tenant-1", agent_id="ag-1",
            action_type="send", platform="email",
            params={"execution_id": "ex-1", "step_id": "s1"},
            status="approved", reviewed_by="owner-1",
        ))
        session_db.commit()
    finally:
        session_db.close()

    @contextmanager
    def _db():
        session = scratch()
        try:
            yield session
        finally:
            session.close()

    governance = MagicMock()
    governance.can_perform_action_async = AsyncMock(
        return_value={"allowed": False, "reason": "maturity too low"})
    governance.request_approval = MagicMock(return_value="hitl-1")
    ws = MagicMock()
    ws.notify_workflow_status = AsyncMock()
    analytics = MagicMock()
    analytics.track_workflow_execution = MagicMock()
    execute = AsyncMock(return_value={"status": "success"})

    workflow = {"id": "wf-1", "agent_id": "ag-1", "steps": [_step()]}

    with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
            patch("core.analytics_engine.get_analytics_engine",
                  return_value=analytics), \
            patch("core.service_factory.ServiceFactory.get_governance_service",
                  return_value=governance), \
            patch.object(workflow_engine_module, "get_db_session", _db), \
            patch.object(engine, "_execute_step", new=execute), \
            patch.object(engine, "_notify_workflow_paused", new=MagicMock()):
        # 1. Denied: pause durably, do not execute.
        await engine._run_execution("ex-1", workflow)
        assert execute.await_count == 0
        paused = [c for c in engine.state_manager.update_execution_status.call_args_list
                  if c.args[1] == "PAUSED"]
        assert paused
        governance.request_approval.assert_called_once()

        # 2. Resume with the durable approval: execute exactly once.
        state["input_data"] = {"approved": True, "hitl_action_id": "hitl-1"}
        await engine._run_execution("ex-1", workflow)
        assert execute.await_count == 1
        consumed = state["input_data"].get("consumed_hitl_action_ids") or []
        assert "hitl-1" in consumed

        # 3. Duplicate resume: the approval is consumed, so it pauses again.
        await engine._run_execution("ex-1", workflow)
        assert execute.await_count == 1
        assert governance.request_approval.call_count == 2


@pytest.mark.asyncio
async def test_boolean_alone_never_authorizes_the_step(engine_free=None):
    engine, state = _engine()
    governance = MagicMock()
    governance.can_perform_action_async = AsyncMock(
        return_value={"allowed": False, "reason": "maturity too low"})
    governance.request_approval = MagicMock(return_value="hitl-x")
    ws = MagicMock()
    ws.notify_workflow_status = AsyncMock()
    analytics = MagicMock()
    execute = AsyncMock(return_value={"status": "success"})
    state["input_data"] = {"approved": True}

    with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
            patch("core.analytics_engine.get_analytics_engine",
                  return_value=analytics), \
            patch("core.service_factory.ServiceFactory.get_governance_service",
                  return_value=governance), \
            patch.object(engine, "_execute_step", new=execute), \
            patch.object(engine, "_notify_workflow_paused", new=MagicMock()):
        await engine._run_execution(
            "ex-1", {"id": "wf-1", "agent_id": "ag-1", "steps": [_step()]})

    assert execute.await_count == 0
    assert governance.request_approval.called
