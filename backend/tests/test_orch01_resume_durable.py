"""ORCH-01 real durable resume/finalization controls.

These use real scratch HITLAction/WorkflowExecution rows and fresh SQLite
sessions. Only governance and the controlled effect seam are doubled; the
durable approval lookup/creation is the production path.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager

import pytest

from advanced_workflow_orchestrator import (
    AdvancedWorkflowOrchestrator,
    WorkflowContext,
    WorkflowDefinition,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepType,
)
from core.intervention_service import intervention_service
from core.models import HITLAction, WorkflowExecution
from tests.test_orch01_workflow_blueprint import (
    _client,
    _configure_model,
    _draft,
    orch_env,
)


def _entity_draft():
    return _draft(name="Controlled durable write", nodes=[{
        "id": "write",
        "type": "entity",
        "name": "Write record",
        "action": {"kind": "write"},
        "metadata": {"entity_name": "record", "entity_type": "record"},
    }])


def _generate_definition(orch_env, monkeypatch):
    state = {"calls": [], "draft": _entity_draft()}
    _configure_model(monkeypatch, state)
    client = _client(orch_env["db"], orch_env["user"])
    response = client.post(
        "/api/v1/workflows/generate-from-agent",
        json={"prompt": "Write one controlled record"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["execution_ready"] is True, body
    assert body["registration"]["registered"] is True
    assert orch_env["fake"].registered
    return orch_env["fake"].registered[0]


def _patch_fresh_sessions(monkeypatch, orch_env):
    Session = orch_env["Session"]

    @contextmanager
    def fresh():
        session = Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    import advanced_workflow_orchestrator as orch_module
    import core.database as database
    import core.intervention_service as intervention_module

    monkeypatch.setattr(database, "get_db_session", fresh)
    monkeypatch.setattr(intervention_module, "get_db_session", fresh)
    monkeypatch.setattr(orch_module, "get_db_session", fresh)
    return fresh


def _real_orchestrator(monkeypatch, definitions, *, governance_status,
                       effects):
    import core.agent_governance_service as governance

    monkeypatch.setattr(
        governance.AgentGovernanceService, "__init__",
        lambda self, db: None)
    monkeypatch.setattr(
        governance.AgentGovernanceService, "enforce_action",
        lambda *args, **kwargs: {
            "proceed": True,
            "status": governance_status,
            "action_required": (
                "WAIT_FOR_APPROVAL"
                if governance_status == "PENDING_APPROVAL" else ""),
        })

    orch = AdvancedWorkflowOrchestrator.__new__(AdvancedWorkflowOrchestrator)
    orch.workflows = {definition.workflow_id: definition
                      for definition in definitions}
    orch.active_contexts = {}
    orch.ai_service = None

    async def conditions(*args, **kwargs):
        return True

    async def dispatch(workflow, step, context):
        if step.step_type == WorkflowStepType.APPROVAL_REQUIRED:
            return await orch._execute_approval_required_step(step, context)
        effects.append(step.step_id)
        return {"status": "completed"}

    orch._check_conditions = conditions
    orch._execute_step_by_type = dispatch
    orch._create_snapshot = lambda *args, **kwargs: None
    return orch


def _approval_step(definition):
    return next(
        step for step in definition.steps
        if step.step_type == WorkflowStepType.APPROVAL_REQUIRED)


def _pause(orch, definition, execution_id):
    return asyncio.run(orch.execute_workflow(
        definition.workflow_id,
        {},
        execution_context={
            "user_id": "user-1",
            "workspace_id": "ws-1",
            "tenant_id": "tenant-1",
        },
        execution_id=execution_id,
    ))


def test_real_pending_then_approved_resume_dispatches_once(
        orch_env, monkeypatch):
    _patch_fresh_sessions(monkeypatch, orch_env)
    definition = _generate_definition(orch_env, monkeypatch)
    effects = []
    orch = _real_orchestrator(
        monkeypatch, [definition],
        governance_status="PENDING_APPROVAL", effects=effects)

    context = _pause(orch, definition, "exec-real-approved")
    assert context.status == WorkflowStatus.WAITING_APPROVAL
    assert effects == []
    approval = _approval_step(definition)
    waiting = context.results[approval.step_id]
    assert waiting["status"] == "waiting_approval"
    action_id = waiting["hitl_action_id"]
    assert action_id

    with orch_env["Session"]() as fresh:
        execution = fresh.query(WorkflowExecution).filter(
            WorkflowExecution.execution_id == "exec-real-approved").one()
        assert execution.status == WorkflowStatus.WAITING_APPROVAL.value
        assert execution.workflow_id == definition.workflow_id
        action = fresh.query(HITLAction).filter(
            HITLAction.id == action_id).one()
        assert action.status == "pending"

    # Pending durable review: no descendant effect.
    asyncio.run(orch.resume_workflow(
        "exec-real-approved", approval.step_id))
    assert effects == []
    assert context.status == WorkflowStatus.WAITING_APPROVAL

    approved = asyncio.run(intervention_service.approve_intervention(
        action_id, "user-1"))
    assert approved["success"] is True, approved

    asyncio.run(orch.resume_workflow(
        "exec-real-approved", approval.step_id))
    assert effects == ["write"], effects
    assert context.status == WorkflowStatus.COMPLETED
    assert context.results[approval.step_id]["approved_at"]

    # Duplicate resume is a no-op, not a second effect.
    asyncio.run(orch.resume_workflow(
        "exec-real-approved", approval.step_id))
    assert effects == ["write"], effects

    with orch_env["Session"]() as fresh:
        action = fresh.query(HITLAction).filter(
            HITLAction.id == action_id).one()
        assert action.status == "approved"
        assert action.reviewed_by == "user-1"
        execution = fresh.query(WorkflowExecution).filter(
            WorkflowExecution.execution_id == "exec-real-approved").one()
        assert execution.status == WorkflowStatus.COMPLETED.value


def test_real_rejected_resume_does_not_dispatch(orch_env, monkeypatch):
    _patch_fresh_sessions(monkeypatch, orch_env)
    definition = _generate_definition(orch_env, monkeypatch)
    effects = []
    orch = _real_orchestrator(
        monkeypatch, [definition],
        governance_status="PENDING_APPROVAL", effects=effects)
    context = _pause(orch, definition, "exec-real-rejected")
    approval = _approval_step(definition)
    action_id = context.results[approval.step_id]["hitl_action_id"]

    rejected = asyncio.run(intervention_service.reject_intervention(
        action_id, "user-1", "not approved"))
    assert rejected["success"] is True, rejected

    asyncio.run(orch.resume_workflow(
        "exec-real-rejected", approval.step_id))
    assert effects == []
    assert context.status == WorkflowStatus.FAILED
    assert context.results[approval.step_id]["status"] == "rejected"


def test_changed_reviewed_material_cannot_use_old_approval(
        orch_env, monkeypatch):
    _patch_fresh_sessions(monkeypatch, orch_env)
    definition = _generate_definition(orch_env, monkeypatch)
    effects = []
    orch = _real_orchestrator(
        monkeypatch, [definition],
        governance_status="PENDING_APPROVAL", effects=effects)
    context = _pause(orch, definition, "exec-real-changed")
    approval = _approval_step(definition)
    action_id = context.results[approval.step_id]["hitl_action_id"]
    approved = asyncio.run(intervention_service.approve_intervention(
        action_id, "user-1"))
    assert approved["success"] is True, approved

    # The human reviewed the empty input; this is a different request.
    context.input_data["amount"] = 999
    asyncio.run(orch.resume_workflow(
        "exec-real-changed", approval.step_id))
    assert effects == []
    assert context.status == WorkflowStatus.FAILED
    assert context.results[approval.step_id]["status"] == "unavailable"

    with orch_env["Session"]() as fresh:
        rows = fresh.query(HITLAction).all()
        assert len(rows) == 1
        assert rows[0].status == "approved"


def test_wrong_workflow_same_step_id_cannot_release_approval(
        orch_env, monkeypatch):
    _patch_fresh_sessions(monkeypatch, orch_env)
    definition_a = _generate_definition(orch_env, monkeypatch)
    effects = []
    orch = _real_orchestrator(
        monkeypatch, [definition_a],
        governance_status="PENDING_APPROVAL", effects=effects)
    context_a = _pause(orch, definition_a, "exec-real-a")
    approval_a = _approval_step(definition_a)
    action_a = context_a.results[approval_a.step_id]["hitl_action_id"]
    approved = asyncio.run(intervention_service.approve_intervention(
        action_a, "user-1"))
    assert approved["success"] is True, approved

    definition_b = WorkflowDefinition(
        workflow_id="wf-same-step-b",
        name="Wrong workflow with the same approval step id",
        description="",
        start_step=approval_a.step_id,
        definition_digest="digest-b",
        steps=[
            WorkflowStep(
                step_id=approval_a.step_id,
                step_type=WorkflowStepType.APPROVAL_REQUIRED,
                description="Approve B",
                parameters={
                    **approval_a.parameters,
                    "guarded_step": "write_b",
                },
                next_steps=["write_b"],
            ),
            WorkflowStep(
                step_id="write_b",
                step_type=WorkflowStepType.ENTITY,
                description="Write B",
                parameters={"action": "create"},
                next_steps=[],
            ),
        ],
    )
    context_b = WorkflowContext(workflow_id="exec-real-b", input_data={})
    context_b.status = WorkflowStatus.WAITING_APPROVAL
    context_b.variables["_workflow_definition_id"] = definition_b.workflow_id
    context_b.variables["_workflow_definition_digest"] = (
        definition_b.definition_digest)
    context_b.results[approval_a.step_id] = {
        "status": "waiting_approval",
        "hitl_action_id": action_a,
    }
    orch.workflows[definition_b.workflow_id] = definition_b
    orch.active_contexts["exec-real-b"] = context_b

    asyncio.run(orch.resume_workflow(
        "exec-real-b", approval_a.step_id))
    assert effects == []
    assert context_b.status == WorkflowStatus.FAILED
    assert context_b.results[approval_a.step_id]["status"] == "unavailable"


def test_successor_block_preserves_failed_outcome(
        orch_env, monkeypatch):
    _patch_fresh_sessions(monkeypatch, orch_env)
    definition = _generate_definition(orch_env, monkeypatch)
    effects = []
    orch = _real_orchestrator(
        monkeypatch, [definition],
        governance_status="PENDING_APPROVAL", effects=effects)
    context = _pause(orch, definition, "exec-real-blocked")
    approval = _approval_step(definition)
    action_id = context.results[approval.step_id]["hitl_action_id"]
    approved = asyncio.run(intervention_service.approve_intervention(
        action_id, "user-1"))
    assert approved["success"] is True, approved

    async def blocked_dispatch(workflow, step, ctx):
        if step.step_type == WorkflowStepType.APPROVAL_REQUIRED:
            return await orch._execute_approval_required_step(step, ctx)
        return {"status": "blocked", "error": "denied"}

    orch._execute_step_by_type = blocked_dispatch
    asyncio.run(orch.resume_workflow(
        "exec-real-blocked", approval.step_id))
    assert effects == []
    assert context.status == WorkflowStatus.FAILED


def _approval_client(db, user):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from core.auth import get_current_user as auth_get_current_user
    from core.database import get_db
    from integrations.workflow_approval_routes import router as approval_router

    app = FastAPI()
    app.include_router(approval_router)
    app.dependency_overrides[auth_get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def test_public_workflow_approval_route_uses_durable_checkpoint(
        orch_env, monkeypatch):
    _patch_fresh_sessions(monkeypatch, orch_env)
    definition = _generate_definition(orch_env, monkeypatch)
    effects = []
    orch = _real_orchestrator(
        monkeypatch, [definition],
        governance_status="PENDING_APPROVAL", effects=effects)
    context = _pause(orch, definition, "exec-route-1")
    approval = _approval_step(definition)
    action_id = context.results[approval.step_id]["hitl_action_id"]
    monkeypatch.setattr(
        "advanced_workflow_orchestrator.get_orchestrator", lambda: orch)
    client = _approval_client(orch_env["db"], orch_env["user"])
    orch_env["db"].expire_all()

    response = client.post(
        "/api/v1/workflows/approvals/exec-route-1/respond",
        json={"decision": "approve", "step_id": approval.step_id})
    assert response.status_code == 200, response.text
    assert effects == ["write"], effects

    with orch_env["Session"]() as fresh:
        action = fresh.query(HITLAction).filter(
            HITLAction.id == action_id).one()
        assert action.status == "approved"
        assert action.reviewed_by == "user-1"

    # Duplicate approval is refused at the execution-status gate and does not
    # dispatch a second effect.
    orch_env["db"].expire_all()
    duplicate = client.post(
        "/api/v1/workflows/approvals/exec-route-1/respond",
        json={"decision": "approve", "step_id": approval.step_id})
    assert duplicate.status_code == 400, duplicate.text
    assert effects == ["write"], effects
