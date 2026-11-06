"""Public workflow approval join — scope, review and one durable effect.

The decisive product contract: a user must be able to find and decide the work
their employee is waiting on, and approving the exact scoped material unlocks
only that material.

These tests drive the real public surfaces:

* ``POST /workflows/{id}/execute`` with the authenticated caller;
* the real ``AgentGovernanceService`` + ``ServiceFactory`` inside the real
  ``WorkflowEngine._run_execution``;
* the real ``GET/POST /api/agents/approvals`` router backed by the real
  ``InterventionService``;
* the real durable ``ExecutionStateManager`` and the real
  ``WorkflowEngine._execute_step`` (the harmless registered ``database``
  action — no transport stub).

Only the authenticated principal and the workflow definition source are
supplied by the test fixture.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func

from api.approvals_routes import router as approvals_router
from core import workflow_endpoints
from core.auth import get_current_user
from core.database import get_db_session
from core.execution_state_manager import ExecutionStateManager
from core.models import (
    AgentRegistry,
    HITLAction,
    Tenant,
    User,
    WorkflowExecution,
    WorkflowExecutionLog,
    WorkflowSnapshot,
    Workspace,
)
from core.workflow_engine import WorkflowEngine, get_workflow_engine

pytestmark = pytest.mark.asyncio


def _suffix() -> str:
    return uuid.uuid4().hex[:10]


def _workflow(workflow_id: str, agent_id: str, record: str = "harmless") -> dict:
    """A real step that resolves through the registered local executor."""
    return {
        "id": workflow_id,
        "name": "Scoped public approval",
        "description": "",
        "version": "1",
        "nodes": [],
        "connections": [],
        "triggers": [],
        "enabled": True,
        "agent_id": agent_id,
        "steps": [{
            "id": "s1",
            "name": "Local database action",
            "service": "database",
            "action": "create",
            "parameters": {"record": record},
            "continue_on_error": False,
            "timeout": None,
            "input_schema": {},
            "output_schema": {},
        }],
    }


def _create_world(*, scope: str = "local") -> dict:
    suffix = _suffix()
    tenant_id = f"tenant-{scope}-{suffix}"
    workspace_id = f"workspace-{scope}-{suffix}"
    user_id = f"reviewer-{scope}-{suffix}"
    agent_id = f"agent-{scope}-{suffix}"
    workflow_id = f"wf-{scope}-{suffix}"
    with get_db_session() as db:
        db.add(Tenant(id=tenant_id, name=f"Tenant {suffix}", subdomain=f"t{suffix}"))
        db.add(Workspace(id=workspace_id, name=f"Workspace {suffix}",
                         tenant_id=tenant_id))
        db.add(User(
            id=user_id, email=f"{user_id}@example.invalid",
            first_name="Scoped", last_name="Reviewer",
            tenant_id=tenant_id, workspace_id=workspace_id,
            role="team_lead", status="active", is_active=True,
        ))
        db.add(AgentRegistry(
            id=agent_id, name=f"Agent {suffix}", category="test",
            module_path="tests.workflow", class_name="ScopedAgent",
            status="student", tenant_id=tenant_id,
            workspace_id=workspace_id,
        ))
        db.commit()
        user = db.query(User).filter(User.id == user_id).first()
        workflow = _workflow(workflow_id, agent_id)
    return {
        "tenant_id": tenant_id, "workspace_id": workspace_id,
        "user": user, "agent_id": agent_id, "workflow": workflow,
        "workflow_id": workflow_id,
    }


def _delete_world(world: dict) -> None:
    workflow_id = world["workflow_id"]
    with get_db_session() as db:
        execution_ids = [
            row.execution_id for row in db.query(WorkflowExecution).filter(
                WorkflowExecution.workflow_id == workflow_id).all()
        ]
        for execution_id in execution_ids:
            db.query(WorkflowExecutionLog).filter(
                WorkflowExecutionLog.execution_id == execution_id).delete()
            db.query(WorkflowSnapshot).filter(
                WorkflowSnapshot.execution_id == execution_id).delete()
        db.query(HITLAction).filter(
            HITLAction.agent_id == world["agent_id"]).delete()
        db.query(WorkflowExecution).filter(
            WorkflowExecution.workflow_id == workflow_id).delete()
        db.query(AgentRegistry).filter(
            AgentRegistry.id == world["agent_id"]).delete()
        db.query(User).filter(User.id == world["user"].id).delete()
        db.query(Workspace).filter(
            Workspace.id == world["workspace_id"]).delete()
        db.query(Tenant).filter(Tenant.id == world["tenant_id"]).delete()
        db.commit()


def _app(world: dict) -> FastAPI:
    app = FastAPI()
    app.include_router(workflow_endpoints.router)
    app.include_router(approvals_router)
    app.dependency_overrides[get_current_user] = lambda: world["user"]
    return app


async def _wait_status(state_manager: ExecutionStateManager, execution_id: str,
                       expected: str, timeout: float = 15.0) -> dict:
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = await state_manager.get_execution_state(execution_id)
        if last and last["status"] == expected:
            return last
        await asyncio.sleep(0.05)
    raise AssertionError(
        f"execution {execution_id} did not reach {expected}; last={last}")


def _dispatch_count(execution_id: str) -> int:
    with get_db_session() as db:
        return db.query(func.count(WorkflowExecutionLog.id)).filter(
            WorkflowExecutionLog.execution_id == execution_id).scalar()


async def _start(client: httpx.AsyncClient, workflow_id: str) -> str:
    response = await client.post(f"/workflows/{workflow_id}/execute", json={})
    assert response.status_code == 200, response.text
    return response.json()["execution_id"]


async def _pending(client: httpx.AsyncClient) -> list:
    response = await client.get("/api/agents/approvals/pending")
    assert response.status_code == 200, response.text
    return response.json()


async def _decide(client: httpx.AsyncClient, action_id: str,
                  decision: str) -> httpx.Response:
    return await client.post(
        f"/api/agents/approvals/{action_id}", json={"decision": decision})


@pytest.fixture
def public_world():
    world = _create_world()
    # The workflow definition source is a fixture input; the engine and all
    # durable state stay real.
    original = workflow_endpoints.load_workflows
    workflow_endpoints.load_workflows = lambda: [world["workflow"]]
    try:
        yield world
    finally:
        workflow_endpoints.load_workflows = original
        _delete_world(world)


@pytest.fixture
def foreign_world():
    world = _create_world(scope="foreign")
    original = workflow_endpoints.load_workflows
    workflow_endpoints.load_workflows = lambda: [world["workflow"]]
    try:
        yield world
    finally:
        workflow_endpoints.load_workflows = original
        _delete_world(world)


async def test_public_workflow_approval_is_visible_decidable_and_resumes_once(
        public_world):
    state_manager = ExecutionStateManager()
    transport = httpx.ASGITransport(app=_app(public_world))
    with patch.object(WorkflowEngine, "_notify_workflow_paused",
                      new=lambda *a, **k: None):
        async with httpx.AsyncClient(
                transport=transport, base_url="http://test") as client:
            execution_id = await _start(client, public_world["workflow_id"])

            # The workflow paused durably before any step dispatch.
            paused = await _wait_status(state_manager, execution_id, "PAUSED")
            assert paused["steps"]["s1"]["status"] == "PAUSED"
            assert _dispatch_count(execution_id) == 0

            pending = await _pending(client)
            assert len(pending) == 1, pending
            approval = pending[0]
            assert approval["action_type"] == "create"
            assert approval["agent_id"] == public_world["agent_id"]
            assert approval["reason"], "the waiting reason must be visible"
            assert approval["params"]["execution_id"] == execution_id
            assert approval["params"]["step_id"] == "s1"

            # Decide through the same public surface, but resume on a fresh
            # engine instance (a restarted worker reads the durable row).
            with patch("core.workflow_engine.get_workflow_engine",
                       return_value=WorkflowEngine()):
                decision = await _decide(client, approval["id"], "approved")
            assert decision.status_code == 200, decision.text
            assert decision.json()["resume"]["resumed"] is True, decision.json()

            completed = await _wait_status(state_manager, execution_id, "COMPLETED")
            assert completed["steps"]["s1"]["status"] == "COMPLETED"
            assert set(completed["outputs"]) == {"s1"}
            assert _dispatch_count(execution_id) == 1

            with get_db_session() as db:
                row = db.query(HITLAction).filter(
                    HITLAction.id == approval["id"]).first()
                assert row.status == "approved"
                assert row.tenant_id == public_world["tenant_id"]
                assert row.workspace_id == public_world["workspace_id"]

            consumed = completed["input_data"].get("consumed_hitl_action_ids") or []
            assert approval["id"] in consumed

            # Duplicate continuation of the same execution must not dispatch
            # the already-completed step again.
            engine = get_workflow_engine()
            await engine._run_execution(execution_id, public_world["workflow"])
            assert _dispatch_count(execution_id) == 1
            again = await state_manager.get_execution_state(execution_id)
            assert again["steps"]["s1"]["status"] == "COMPLETED"
            assert set(again["outputs"]) == {"s1"}


async def test_resume_inputs_cannot_rewrite_the_frozen_scope(public_world):
    from core.intervention_service import intervention_service
    from core.workflow_engine import EXECUTION_SCOPE_KEY

    state_manager = ExecutionStateManager()
    transport = httpx.ASGITransport(app=_app(public_world))
    with patch.object(WorkflowEngine, "_notify_workflow_paused",
                      new=lambda *a, **k: None):
        async with httpx.AsyncClient(
                transport=transport, base_url="http://test") as client:
            execution_id = await _start(client, public_world["workflow_id"])
            await _wait_status(state_manager, execution_id, "PAUSED")
            approval = (await _pending(client))[0]

            approved = await intervention_service.approve_intervention(
                approval["id"], public_world["user"].id)
            assert approved["success"] is True, approved

            engine = get_workflow_engine()
            resumed = await engine.resume_workflow(
                execution_id, public_world["workflow"], {
                    "approved": True,
                    "hitl_action_id": approval["id"],
                    # A caller cannot move the run into another tenant.
                    EXECUTION_SCOPE_KEY: {
                        "workspace_id": "workspace-foreign",
                        "tenant_id": "tenant-foreign",
                    },
                })
            assert resumed is True
            completed = await _wait_status(
                state_manager, execution_id, "COMPLETED")
            assert _dispatch_count(execution_id) == 1
            assert approval["id"] in (
                completed["input_data"].get("consumed_hitl_action_ids") or [])
            with get_db_session() as db:
                row = db.query(HITLAction).filter(
                    HITLAction.id == approval["id"]).first()
                assert row.tenant_id == public_world["tenant_id"]
                assert row.workspace_id == public_world["workspace_id"]


async def test_schedule_freezes_caller_scope_and_discards_client_scope(
        public_world):
    from ai.workflow_scheduler import workflow_scheduler
    from core.workflow_engine import EXECUTION_SCOPE_KEY

    captured = {}

    def _capture(workflow_id, trigger_type, trigger_config,
                 input_data=None, authorized=False):
        captured["input_data"] = input_data
        return "job-scope-test"

    transport = httpx.ASGITransport(app=_app(public_world))
    with patch.object(workflow_scheduler, "schedule_workflow",
                      side_effect=_capture):
        async with httpx.AsyncClient(
                transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/workflows/{public_world['workflow_id']}/schedule",
                json={
                    "trigger_type": "interval",
                    "trigger_config": {"minutes": 30},
                    "input_data": {
                        "x": 1,
                        # A client cannot choose the deferred run's scope.
                        EXECUTION_SCOPE_KEY: {
                            "workspace_id": "workspace-foreign",
                            "tenant_id": "tenant-foreign",
                        },
                    },
                })
    assert response.status_code == 200, response.text
    assert captured["input_data"]["x"] == 1
    assert captured["input_data"][EXECUTION_SCOPE_KEY] == {
        "workspace_id": public_world["workspace_id"],
        "tenant_id": public_world["tenant_id"],
    }


async def test_public_workflow_rejection_leaves_zero_effect(public_world):
    state_manager = ExecutionStateManager()
    transport = httpx.ASGITransport(app=_app(public_world))
    with patch.object(WorkflowEngine, "_notify_workflow_paused",
                      new=lambda *a, **k: None):
        async with httpx.AsyncClient(
                transport=transport, base_url="http://test") as client:
            execution_id = await _start(client, public_world["workflow_id"])
            await _wait_status(state_manager, execution_id, "PAUSED")
            approval = (await _pending(client))[0]

            decision = await _decide(client, approval["id"], "rejected")
            assert decision.status_code == 200, decision.text
            failed = await _wait_status(state_manager, execution_id, "FAILED")

            assert failed["outputs"] == {}
            assert _dispatch_count(execution_id) == 0
            with get_db_session() as db:
                row = db.query(HITLAction).filter(
                    HITLAction.id == approval["id"]).first()
                assert row.status == "rejected"


async def test_changed_material_after_review_does_not_execute(public_world):
    state_manager = ExecutionStateManager()
    transport = httpx.ASGITransport(app=_app(public_world))
    with patch.object(WorkflowEngine, "_notify_workflow_paused",
                      new=lambda *a, **k: None):
        async with httpx.AsyncClient(
                transport=transport, base_url="http://test") as client:
            execution_id = await _start(client, public_world["workflow_id"])
            await _wait_status(state_manager, execution_id, "PAUSED")
            approval = (await _pending(client))[0]

            # The guarded material changes after review: the old approval
            # must not authorize the new payload.
            public_world["workflow"]["steps"][0]["parameters"] = {
                "record": "changed-after-review"}

            decision = await _decide(client, approval["id"], "approved")
            assert decision.status_code == 200, decision.text
            paused = await _wait_status(state_manager, execution_id, "PAUSED")

            assert paused["outputs"] == {}
            assert _dispatch_count(execution_id) == 0
            with get_db_session() as db:
                rows = db.query(HITLAction).filter(
                    HITLAction.agent_id == public_world["agent_id"]).all()
                bound = [
                    row for row in rows
                    if (row.params or {}).get("execution_id") == execution_id
                ]
                assert {row.status for row in bound} == {"pending", "approved"}


@pytest.mark.parametrize("foreign_scope", ["workspace", "tenant"])
async def test_foreign_scope_cannot_see_or_decide_public_workflow_approval(
        public_world, foreign_scope):
    state_manager = ExecutionStateManager()
    app = _app(public_world)
    transport = httpx.ASGITransport(app=app)
    with patch.object(WorkflowEngine, "_notify_workflow_paused",
                      new=lambda *a, **k: None):
        async with httpx.AsyncClient(
                transport=transport, base_url="http://test") as client:
            execution_id = await _start(client, public_world["workflow_id"])
            await _wait_status(state_manager, execution_id, "PAUSED")
            approval = (await _pending(client))[0]

            suffix = _suffix()
            tenant_id = public_world["tenant_id"]
            if foreign_scope == "tenant":
                tenant_id = f"tenant-other-{suffix}"
                with get_db_session() as db:
                    db.add(Tenant(id=tenant_id, name="Other", subdomain=f"o{suffix}"))
                    db.commit()
            workspace_id = f"workspace-other-{suffix}"
            user_id = f"reviewer-other-{suffix}"
            with get_db_session() as db:
                db.add(Workspace(id=workspace_id, name="Other", tenant_id=tenant_id))
                db.add(User(
                    id=user_id, email=f"{user_id}@example.invalid",
                    first_name="Other", last_name="Reviewer", role="team_lead",
                    tenant_id=tenant_id, workspace_id=workspace_id,
                    status="active", is_active=True,
                ))
                db.commit()
                foreign_user = db.query(User).filter(User.id == user_id).first()

            app.dependency_overrides[get_current_user] = lambda: foreign_user
            try:
                assert await _pending(client) == []
                decision = await _decide(client, approval["id"], "approved")
                assert decision.status_code == 404, decision.text
            finally:
                app.dependency_overrides[get_current_user] = (
                    lambda: public_world["user"])
                with get_db_session() as db:
                    db.query(User).filter(User.id == user_id).delete()
                    db.query(Workspace).filter(
                        Workspace.id == workspace_id).delete()
                    if foreign_scope == "tenant":
                        db.query(Tenant).filter(Tenant.id == tenant_id).delete()
                    db.commit()

            with get_db_session() as db:
                assert db.query(HITLAction).filter(
                    HITLAction.id == approval["id"]).first().status == "pending"
