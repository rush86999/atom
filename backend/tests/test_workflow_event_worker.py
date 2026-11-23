"""Concrete event startup drain with real scratch state and engine claims."""
import asyncio
from unittest.mock import AsyncMock, Mock
import pytest
from core import workflow_event_worker as worker
from core.execution_state_manager import ExecutionStateManager
from core.workflow_engine import WorkflowEngine
from tests.test_workflow_event_reservation import IDENTITY, event_db


async def reserved(manager, name):
    workflow = {"id": "workflow", "enabled": True, "steps": [
        {"id": "one", "service": "synthetic", "action": "work", "parameters": {}}]}
    state, created = await manager.reserve_event_execution(
        "workflow", {}, execution_id=name, identity=IDENTITY,
        admission={"execution_id": name, "workflow_id": "workflow",
                   "owner_id": IDENTITY["user_id"], "tenant_id": IDENTITY["tenant_id"],
                   "workspace_id": IDENTITY["workspace_id"], "workflow_snapshot": workflow,
                   "connection_id": "connection-one", "source": "synthetic-mail"})
    assert created
    return state


def engine_for(manager):
    engine = WorkflowEngine()
    engine.state_manager = manager
    engine._run_execution = AsyncMock()
    engine._publish_orchestration_event = Mock()
    return engine


async def finish(engine):
    if engine._background_tasks:
        await asyncio.gather(*list(engine._background_tasks))


def test_restart_drain_uses_real_manager_and_reserved_launch(event_db):
    async def check():
        await reserved(ExecutionStateManager(), "evt_restart")
        manager = ExecutionStateManager()
        engine = engine_for(manager)
        assert await worker.process_pending_event_executions_once(
            engine=engine, preflight=AsyncMock(return_value=True)) == 1
        await finish(engine)
        assert (await manager.get_execution_state("evt_restart"))["status"] == "RUNNING"
        engine._run_execution.assert_awaited_once()
        assert await worker.process_pending_event_executions_once(
            engine=engine, preflight=AsyncMock(return_value=True)) == 0
        engine._run_execution.assert_awaited_once()
    asyncio.run(check())


@pytest.mark.parametrize("permanent", [True, False])
def test_refused_or_deferred_first_does_not_hide_second(event_db, permanent):
    async def check():
        manager = ExecutionStateManager()
        for name in ("evt_a_blocked", "evt_b_ready"):
            await reserved(manager, name)
        engine = engine_for(manager)
        async def preflight(execution_id, state, workflow):
            if execution_id == "evt_a_blocked":
                if permanent:
                    raise worker._PermanentRefusal("owner_inactive")
                raise RuntimeError("temporary synthetic dependency failure")
            return True
        assert await worker.process_pending_event_executions_once(
            limit=2, engine=engine, preflight=preflight) == 1
        await finish(engine)
        assert (await manager.get_execution_state("evt_a_blocked"))["status"] == (
            "FAILED" if permanent else "PENDING")
        assert (await manager.get_execution_state("evt_b_ready"))["status"] == "RUNNING"
        engine._run_execution.assert_awaited_once()
    asyncio.run(check())


def test_deferred_page_advances_across_ticks_and_wraps(event_db):
    async def check():
        manager = ExecutionStateManager()
        for name in ("evt_a_deferred", "evt_b_deferred", "evt_c_ready"):
            await reserved(manager, name)
        engine = engine_for(manager)
        async def preflight(execution_id, state, workflow):
            return execution_id == "evt_c_ready"
        assert await worker.process_pending_event_executions_once(2, engine=engine, preflight=preflight) == 0
        assert await worker.process_pending_event_executions_once(2, engine=engine, preflight=preflight) == 1
        await finish(engine)
        assert await worker.process_pending_event_executions_once(2, engine=engine, preflight=preflight) == 0
        assert manager._pending_event_scan_cursor is None
        assert await worker.process_pending_event_executions_once(2, engine=engine, preflight=preflight) == 0
        assert manager._pending_event_scan_cursor == "evt_b_deferred"
        engine._run_execution.assert_awaited_once()
    asyncio.run(check())


def test_peer_claim_wins_before_refusal(event_db):
    async def check():
        manager = ExecutionStateManager()
        await reserved(manager, "evt_race")
        engine = engine_for(manager)
        async def preflight(execution_id, state, workflow):
            assert await ExecutionStateManager().claim_event_execution(execution_id)
            raise worker._PermanentRefusal("stale_refusal")
        assert await worker.process_pending_event_executions_once(
            engine=engine, preflight=preflight) == 0
        assert (await manager.get_execution_state("evt_race"))["status"] == "RUNNING"
        engine._run_execution.assert_not_awaited()
    asyncio.run(check())


def test_worker_owns_one_task_and_awaits_stop(monkeypatch):
    async def check():
        observed = asyncio.Event()
        async def tick():
            observed.set()
        monkeypatch.setattr(worker, "process_pending_event_executions_once", tick)
        assert worker.start_workflow_event_worker()
        assert not worker.start_workflow_event_worker()
        task = worker._worker_task
        await asyncio.wait_for(observed.wait(), 2)
        await worker.stop_workflow_event_worker()
        assert task.done()
        assert worker._worker_task is None
    asyncio.run(check())


@pytest.mark.parametrize("case", ["valid", "inactive", "moved_scope", "definition_changed", "missing_definition", "critical_member", "catalog_unavailable", "revoked_connection"])
def test_default_preflight_reads_current_owner_and_definition(event_db, monkeypatch, tmp_path, case):
    import copy
    from contextlib import contextmanager
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from core.models import User, UserConnection
    from core import workflow_endpoints
    db_engine = create_engine(f"sqlite:///{tmp_path / 'owner.db'}")
    User.__table__.create(db_engine)
    UserConnection.__table__.create(db_engine)
    with Session(db_engine) as db:
        db.add(User(id=IDENTITY["user_id"], email="synthetic@example.invalid",
                    first_name="Synthetic", last_name="Owner", role="member",
                    status="active", is_active=case != "inactive",
                    tenant_id=IDENTITY["tenant_id"], workspace_id=(
                        "moved" if case == "moved_scope" else IDENTITY["workspace_id"])))
        db.add(UserConnection(id="connection-one", user_id=IDENTITY["user_id"],
                             tenant_id=IDENTITY["tenant_id"], workspace_id=IDENTITY["workspace_id"],
                             integration_id="synthetic-mail", connection_name="Synthetic source", credentials={},
                             status="revoked" if case == "revoked_connection" else "active"))
        db.commit()
    @contextmanager
    def open_db():
        with Session(db_engine) as db:
            yield db
    monkeypatch.setattr(worker, "_open_db", open_db)
    async def check():
        manager = ExecutionStateManager()
        state = await reserved(manager, "evt_authority")
        snapshot = state["context"]["_atom_event_admission"]["workflow_snapshot"]
        if case == "critical_member":
            snapshot["steps"][0].update(service="mcp", action="email_send")
        current = copy.deepcopy(snapshot)
        if case == "definition_changed":
            current["steps"][0]["parameters"]["changed"] = True
        def load_catalog():
            if case == "catalog_unavailable":
                raise workflow_endpoints.WorkflowStoreUnreadable("synthetic unreadable store")
            return [] if case == "missing_definition" else [current]
        monkeypatch.setattr(workflow_endpoints, "load_workflows_strict", load_catalog)
        monkeypatch.setattr(workflow_endpoints, "_load_template_definition", lambda *a: None)
        before = copy.deepcopy(snapshot)
        if case == "valid":
            assert await worker.dispatch_preflight("evt_authority", state, snapshot)
        elif case == "catalog_unavailable":
            engine = engine_for(manager)
            assert await worker.process_pending_event_executions_once(engine=engine) == 0
            assert (await manager.get_execution_state("evt_authority"))["status"] == "PENDING"
            engine._run_execution.assert_not_awaited()
        else:
            with pytest.raises(worker._PermanentRefusal):
                await worker.dispatch_preflight("evt_authority", state, snapshot)
        assert snapshot == before
    asyncio.run(check())
