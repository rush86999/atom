"""Scheduled real-workflow approval join across a separate OS process.

The accepted #682-#684 scope (and Agent3's continuation) restarts the
scheduler *instance* in the same process/loop. This adds the separate-process
twin: a persisted date job is scheduled, the scheduler is shut down, and a
new Python process starts a new scheduler on the same jobstore. The real
``_execute_job`` fires, the real durable engine pauses for governance, and
the parent process decides/resumes to one recorded local result. A second
fresh process must not re-fire the spent job.

Only the workflow-definition source is supplied to the child; the scheduler
entry, WorkflowEngine, durable state manager and ``_execute_step`` are real.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from ai.workflow_scheduler import WorkflowScheduler
from core import workflow_endpoints
from core.database import DATABASE_URL as APP_DATABASE_URL
from core.database import get_db_session
from core.execution_state_manager import ExecutionStateManager
from core.models import WorkflowExecution
from core.workflow_engine import WorkflowEngine, freeze_execution_scope
from tests.test_workflow_public_approval_flow import (
    _app,
    _create_world,
    _decide,
    _delete_world,
    _dispatch_count,
    _pending,
    _wait_execution_for_workflow,
    _wait_status,
)

pytestmark = pytest.mark.asyncio

# The child starts a fresh scheduler on the persisted jobstore. It uses the
# real async scheduler loop so the job callback and the engine's background
# task can run; a blocking sleep would starve both.
_CHILD_SCRIPT = r"""
import asyncio
import json
import os

import core.workflow_endpoints as workflow_endpoints
from ai.workflow_scheduler import WorkflowScheduler

workflow = json.loads(os.environ["ATOM_TEST_WORKFLOW"])
workflow_endpoints.load_workflows = lambda: [workflow]

async def main():
    scheduler = WorkflowScheduler(db_url=os.environ["ATOM_TEST_JOBSTORE"])
    scheduler.reschedule_system_pipelines = lambda: None
    scheduler.start()
    await asyncio.sleep(float(os.environ.get("ATOM_TEST_CHILD_SLEEP", "12")))
    scheduler.shutdown()

asyncio.run(main())
"""


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_child(job_db: Path, workflow: dict, sleep_seconds: float = 12.0) -> str:
    env = os.environ.copy()
    env.update({
        "TESTING": "1",
        # Pin to the parent engine's actual DB. Earlier tests can rewrite the
        # process env DATABASE_URL without changing the already-created engine.
        "DATABASE_URL": APP_DATABASE_URL,
        "ATOM_TEST_WORKFLOW": json.dumps(workflow),
        "ATOM_TEST_JOBSTORE": f"sqlite:///{job_db}",
        "ATOM_TEST_CHILD_SLEEP": str(sleep_seconds),
    })
    completed = subprocess.run(
        [sys.executable, "-c", _CHILD_SCRIPT],
        cwd=str(_backend_dir()),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, (
        f"child scheduler failed rc={completed.returncode}\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}")
    return completed.stdout + completed.stderr


def _execution_count(workflow_id: str) -> int:
    with get_db_session() as db:
        return db.query(WorkflowExecution).filter(
            WorkflowExecution.workflow_id == workflow_id).count()


async def test_scheduled_approval_join_survives_a_separate_process_restart(
        tmp_path):
    world = _create_world()
    original = workflow_endpoints.load_workflows
    workflow_endpoints.load_workflows = lambda: [world["workflow"]]
    job_db = tmp_path / "process-restart-jobs.db"
    state_manager = ExecutionStateManager()
    try:
        # Schedule in this process, then shut the scheduler down BEFORE the
        # run_date so the fire can only come from the new process.
        first = WorkflowScheduler(db_url=f"sqlite:///{job_db}")
        first.reschedule_system_pipelines = lambda: None
        first.start()
        first.schedule_workflow(
            world["workflow_id"], "date",
            {"run_date": datetime.now(timezone.utc) + timedelta(seconds=8)},
            freeze_execution_scope(
                {},
                workspace_id=world["workspace_id"],
                tenant_id=world["tenant_id"],
            ),
            authorized=False,
        )
        first.shutdown()

        # A separate OS process starts a new scheduler on the same jobstore.
        with patch.object(WorkflowEngine, "_notify_workflow_paused",
                          new=lambda *a, **k: None):
            first_output = _run_child(
                job_db, world["workflow"], sleep_seconds=14)
            assert "Scheduled execution" in first_output, first_output

            execution_id = await _wait_execution_for_workflow(
                world["workflow_id"], timeout=30)
            paused = await _wait_status(
                state_manager, execution_id, "PAUSED", timeout=20)
            assert paused["steps"]["s1"]["status"] == "PAUSED"
            assert _dispatch_count(execution_id) == 0

            transport = httpx.ASGITransport(app=_app(world))
            async with httpx.AsyncClient(
                    transport=transport, base_url="http://test") as client:
                pending = await _pending(client)
                assert len(pending) == 1, pending
                approval = pending[0]
                assert approval["params"]["execution_id"] == execution_id
                decision = await _decide(client, approval["id"], "approved")
                assert decision.status_code == 200, decision.text

            completed = await _wait_status(
                state_manager, execution_id, "COMPLETED")
            assert completed["steps"]["s1"]["status"] == "COMPLETED"
            assert _dispatch_count(execution_id) == 1
            assert approval["id"] in (
                completed["input_data"].get("consumed_hitl_action_ids") or [])

            # A second fresh process must not re-fire the spent date job.
            second_output = _run_child(
                job_db, world["workflow"], sleep_seconds=5)
            assert "Scheduled execution" not in second_output, second_output
            assert _execution_count(world["workflow_id"]) == 1
            assert _dispatch_count(execution_id) == 1
    finally:
        workflow_endpoints.load_workflows = original
        _delete_world(world)
