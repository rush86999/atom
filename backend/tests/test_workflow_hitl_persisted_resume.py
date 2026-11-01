"""WF-05 on the REAL persisted state manager, not an in-memory fake.

Deny -> persisted pause -> durable approval -> execute once -> a NEW engine
instance resumes with the consumed approval and performs zero additional
transport calls.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core import workflow_engine as workflow_engine_module
from core.database import ASYNC_DB_AVAILABLE, get_async_db_session, get_db_session
from core.execution_state_manager import ExecutionStateManager
from core.models import HITLAction
from core.workflow_engine import WorkflowEngine

pytestmark = pytest.mark.skipif(
    not ASYNC_DB_AVAILABLE, reason="async database support unavailable")


def _step():
    return {
        "id": "s1", "name": "Send decision", "service": "email",
        "action": "send", "parameters": {}, "continue_on_error": False,
        "timeout": None, "input_schema": {}, "output_schema": {},
    }


def _engine(state_manager):
    sm = state_manager or MagicMock()
    with patch("core.workflow_engine.get_state_manager", return_value=sm):
        engine = WorkflowEngine()
    engine.state_manager = state_manager
    return engine


async def _cleanup(execution_id: str) -> None:
    from sqlalchemy import delete

    from core.models import WorkflowExecution

    async with get_async_db_session() as db:
        await db.execute(delete(WorkflowExecution).where(
            WorkflowExecution.execution_id == execution_id))
        await db.commit()


@pytest.mark.asyncio
async def test_persisted_pause_approval_resume_once_new_engine():
    suffix = uuid.uuid4().hex[:8]
    hitl_id = f"hitl-persisted-{suffix}"
    agent_id = f"agent-persisted-{suffix}"
    workflow = {
        "id": f"wf-persisted-{suffix}", "agent_id": agent_id,
        "steps": [_step()],
    }

    # Registry agent row + approved HITL row in the shared scratch store.
    with get_db_session() as db:
        from core.models import AgentRegistry

        db.add(AgentRegistry(
            id=agent_id, name=agent_id, category="test",
            module_path="tests.workflow", class_name="PersistedAgent",
            tenant_id="default", workspace_id="default"))
        db.commit()
        db.add(HITLAction(
            id=hitl_id, tenant_id="default", agent_id=agent_id,
            action_type="send", platform="email",
            params={"execution_id": "", "step_id": "s1"},
            status="approved", reviewed_by="owner-1"))
        db.commit()

    state_manager = ExecutionStateManager()
    execution_id = await state_manager.create_execution(
        workflow["id"], {})
    try:
        # Bind the HITL row to the real execution id.
        with get_db_session() as db:
            row = db.query(HITLAction).filter(HITLAction.id == hitl_id).first()
            row.params = {"execution_id": execution_id, "step_id": "s1"}
            db.commit()

        governance = MagicMock()
        governance.can_perform_action_async = AsyncMock(
            return_value={"allowed": False, "reason": "maturity too low"})
        governance.request_approval = MagicMock(return_value=hitl_id)
        ws = MagicMock()
        ws.notify_workflow_status = AsyncMock()
        analytics = MagicMock()
        execute = AsyncMock(return_value={"status": "success"})

        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
                patch("core.analytics_engine.get_analytics_engine",
                      return_value=analytics), \
                patch("core.service_factory.ServiceFactory.get_governance_service",
                      return_value=governance), \
                patch.object(WorkflowEngine, "_notify_workflow_paused",
                             new=MagicMock()):
            engine1 = _engine(state_manager)
            engine1._execute_step = execute
            await engine1._run_execution(execution_id, workflow)
            assert execute.await_count == 0
            persisted = await state_manager.get_execution_state(execution_id)
            assert persisted["status"] == "PAUSED"

            # Human approves; resume on the SAME engine.
            await state_manager.update_execution_inputs(
                execution_id, {"approved": True, "hitl_action_id": hitl_id})
            await state_manager.update_execution_status(
                execution_id, "RUNNING")
            await engine1._run_execution(execution_id, workflow)
            assert execute.await_count == 1

            # A NEW engine instance resumes the persisted execution.
            engine2 = _engine(state_manager)
            engine2._execute_step = execute
            await engine2._run_execution(execution_id, workflow)
            assert execute.await_count == 1, (
                "a consumed approval must not authorize a second transport call")

        consumed = (await state_manager.get_execution_state(
            execution_id))["input_data"].get("consumed_hitl_action_ids") or []
        assert hitl_id in consumed
    finally:
        await _cleanup(execution_id)
        with get_db_session() as db:
            row = db.query(HITLAction).filter(HITLAction.id == hitl_id).first()
            if row is not None:
                db.delete(row)
                db.commit()
