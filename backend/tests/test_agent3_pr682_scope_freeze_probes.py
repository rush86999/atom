"""Agent 3 independent probes for merged PR682 execution-scope freezing.

Independent review of the owner-merged #682 workflow approval-scope repair at
main ``3925cf359`` (runtime source ``068abd57a``, merge ``49d45c7f3``,
scheduled join #684 ``78d2e0ca8``). Adds only the cases the merged controls
do not cover:

1. the direct public execute route must discard a client-supplied
   ``_atom_execution_scope`` (the merged suite covers the schedule route
   only) — the durable execution and the governance approval must carry the
   authenticated caller's scope;
2. the pure helper contract: client key discarded before the authoritative
   scope is set, empty/whitespace scope is not invented, and resume inputs
   are stripped;
3. the scheduler-restart join (Agent 3 review continuation): a persisted
   scheduled job with frozen scope fires on the SECOND scheduler instance
   with the real engine, the approval lands in the scheduling user's own
   queue and resumes to exactly one durable effect; a spent one-shot job
   never refires after a further restart (PR676's counter-callback
   mechanism, joined with the real engine and the approval path).

Reuses the merged suite's real public surfaces, real durable state manager,
real governance service and real ``_execute_step`` database leaf unchanged.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx
import pytest

from core.database import get_db_session
from core.execution_state_manager import ExecutionStateManager
from core.models import HITLAction, WorkflowExecution
from core.workflow_engine import (
    EXECUTION_SCOPE_KEY,
    WorkflowEngine,
    freeze_execution_scope,
    strip_execution_scope,
)

from tests.test_workflow_public_approval_flow import (
    _app,
    _decide,
    _dispatch_count,
    _pending,
    _wait_execution_for_workflow,
    _wait_status,
    public_world,
)


@pytest.mark.asyncio
async def test_execute_route_discards_client_supplied_scope(public_world):
    """A caller cannot smuggle a foreign execution scope through
    ``POST /workflows/{id}/execute`` input_data: the durable execution and
    the governance-created approval carry the authenticated caller's scope.

    The route's lone dict body parameter IS the input_data (FastAPI does not
    embed it), so the client key arrives at the top level where the freeze
    must discard it before setting the caller's authoritative scope."""
    state_manager = ExecutionStateManager()
    transport = httpx.ASGITransport(app=_app(public_world))
    with patch.object(WorkflowEngine, "_notify_workflow_paused",
                      new=lambda *a, **k: None):
        async with httpx.AsyncClient(
                transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/workflows/{public_world['workflow_id']}/execute",
                json={
                    "x": 1,
                    EXECUTION_SCOPE_KEY: {
                        "workspace_id": "workspace-foreign",
                        "tenant_id": "tenant-foreign",
                    },
                })
            assert response.status_code == 200, response.text
            execution_id = response.json()["execution_id"]

            paused = await _wait_status(state_manager, execution_id, "PAUSED")
            assert paused["steps"]["s1"]["status"] == "PAUSED"

            with get_db_session() as db:
                row = db.query(WorkflowExecution).filter(
                    WorkflowExecution.execution_id == execution_id).first()
                assert row is not None
                durable = row.input_data
                if isinstance(durable, str):
                    durable = json.loads(durable or "{}")
                assert durable["x"] == 1
                assert durable[EXECUTION_SCOPE_KEY] == {
                    "workspace_id": public_world["workspace_id"],
                    "tenant_id": public_world["tenant_id"],
                }

            # The approval is waiting in the caller's own scope — a smuggled
            # foreign scope would have moved the row out of this queue.
            pending = await _pending(client)
            assert len(pending) == 1, pending
            with get_db_session() as db:
                approval = db.query(HITLAction).filter(
                    HITLAction.id == pending[0]["id"]).first()
                assert approval.tenant_id == public_world["tenant_id"]
                assert approval.workspace_id == public_world["workspace_id"]


def test_freeze_and_strip_helpers_discard_client_key_and_invent_nothing():
    foreign = {
        "workspace_id": "workspace-foreign",
        "tenant_id": "tenant-foreign",
    }
    frozen = freeze_execution_scope(
        {"x": 1, EXECUTION_SCOPE_KEY: foreign},
        workspace_id="ws-real", tenant_id=None)
    assert frozen["x"] == 1
    assert frozen[EXECUTION_SCOPE_KEY] == {"workspace_id": "ws-real"}

    # Missing or whitespace-only scope values are not invented.
    assert freeze_execution_scope(None, workspace_id="  ") == {}
    assert freeze_execution_scope({"x": 1}) == {"x": 1}

    # Resume inputs are stripped of the reserved key.
    assert strip_execution_scope(
        {"x": 1, EXECUTION_SCOPE_KEY: foreign}) == {"x": 1}
    assert strip_execution_scope(None) == {}


def _make_scheduler(db_path):
    """Real scheduler on a persisted jobstore; only system-pipeline
    reseeding is stubbed (unrelated jobs), exactly like PR676's controls.
    Scheduling is explicit so a restarted instance only LOADS the store."""
    from ai.workflow_scheduler import WorkflowScheduler

    scheduler = WorkflowScheduler(db_url=f"sqlite:///{db_path}")
    scheduler.reschedule_system_pipelines = lambda: None
    scheduler.start()
    return scheduler


def _schedule_fire(scheduler, workspace_id, tenant_id, seconds: float):
    frozen = freeze_execution_scope(
        {}, workspace_id=workspace_id, tenant_id=tenant_id)
    return scheduler.schedule_workflow(
        _scheduled_workflow_id[0], "date",
        {"run_date": datetime.now(timezone.utc) + timedelta(seconds=seconds)},
        frozen, authorized=False)


_scheduled_workflow_id = [None]


@pytest.mark.asyncio
async def test_scheduled_approval_fires_after_restart_with_caller_scope(
        public_world, tmp_path):
    """Restart BEFORE the fire: the persisted job with frozen scope fires on
    the second scheduler instance through the real engine, pauses for
    governance, waits in the scheduling user's own queue, and resumes to
    exactly one durable effect."""
    from ai.workflow_scheduler import WorkflowScheduler

    _scheduled_workflow_id[0] = public_world["workflow_id"]
    db_path = tmp_path / "agent3-restart-approval.db"
    state_manager = ExecutionStateManager()

    first = _make_scheduler(db_path)
    _schedule_fire(first, public_world["workspace_id"],
                   public_world["tenant_id"], 2.0)
    first.shutdown()  # restart before the fire date

    # The restarted instance only loads the persisted store — no new job.
    second = _make_scheduler(db_path)
    try:
        with patch.object(WorkflowEngine, "_notify_workflow_paused",
                          new=lambda *a, **k: None):
            execution_id = await _wait_execution_for_workflow(
                public_world["workflow_id"])
            paused = await _wait_status(state_manager, execution_id, "PAUSED")
            assert paused["steps"]["s1"]["status"] == "PAUSED"
            assert _dispatch_count(execution_id) == 0

            # The frozen scope survived the restart: the approval waits in
            # the scheduling user's own queue.
            transport = httpx.ASGITransport(app=_app(public_world))
            async with httpx.AsyncClient(
                    transport=transport, base_url="http://test") as client:
                pending = await _pending(client)
                assert len(pending) == 1, pending
                assert pending[0]["params"]["execution_id"] == execution_id
                decision = await _decide(client, pending[0]["id"], "approved")
                assert decision.status_code == 200, decision.text

            completed = await _wait_status(
                state_manager, execution_id, "COMPLETED")
            assert completed["steps"]["s1"]["status"] == "COMPLETED"
            assert _dispatch_count(execution_id) == 1
            assert pending[0]["id"] in (
                completed["input_data"].get("consumed_hitl_action_ids") or [])
            with get_db_session() as db:
                row = db.query(HITLAction).filter(
                    HITLAction.id == pending[0]["id"]).first()
                assert row.tenant_id == public_world["tenant_id"]
                assert row.workspace_id == public_world["workspace_id"]
    finally:
        second.shutdown()


@pytest.mark.asyncio
async def test_spent_scheduled_approval_never_refires_after_restart(
        public_world, tmp_path):
    """Restart AFTER the fire completed: a spent one-shot job creates no new
    execution and dispatches nothing (PR676's no-duplicate control, joined
    with the real engine and approval path)."""
    from ai.workflow_scheduler import WorkflowScheduler

    _scheduled_workflow_id[0] = public_world["workflow_id"]
    db_path = tmp_path / "agent3-spent-approval.db"
    state_manager = ExecutionStateManager()

    first = _make_scheduler(db_path)
    _schedule_fire(first, public_world["workspace_id"],
                   public_world["tenant_id"], 0.4)
    try:
        with patch.object(WorkflowEngine, "_notify_workflow_paused",
                          new=lambda *a, **k: None):
            execution_id = await _wait_execution_for_workflow(
                public_world["workflow_id"])
            await _wait_status(state_manager, execution_id, "PAUSED")
            # Let the fire finish and APScheduler remove the spent one-shot
            # before shutting down (same settle as PR676's controls).
            await asyncio.sleep(0.5)
    finally:
        first.shutdown()

    def _execution_count():
        with get_db_session() as db:
            return db.query(WorkflowExecution).filter(
                WorkflowExecution.workflow_id ==
                public_world["workflow_id"]).count()

    assert _execution_count() == 1
    second = _make_scheduler(db_path)
    try:
        await asyncio.sleep(1.0)
        assert _execution_count() == 1, (
            "spent one-shot job refired after scheduler restart")
        assert _dispatch_count(execution_id) == 0
    finally:
        second.shutdown()
