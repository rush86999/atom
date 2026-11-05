"""ORCH-01 real checkpoint durability controls.

These controls use a real scratch SQLite database and real ``HITLAction``
rows. They deliberately do not mock ``_find_durable_approval`` or
``_create_durable_approval``; only governance and the effect dispatch are
controlled seams. A fresh orchestrator/session resumes each run so an
in-memory context cannot stand in for durable state.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from advanced_workflow_orchestrator import (
    AdvancedWorkflowOrchestrator,
    WorkflowDefinition,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepType,
)
from core.agents.workflow_blueprint import compile_blueprint
from core.database import Base
from core.models import HITLAction, Tenant, User, Workspace, WorkflowExecution


SCOPE = {"workspace_id": "ws-real", "tenant_id": "tenant-real"}
APPROVER_ID = "approver-1"


@pytest.fixture()
def real_db(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path}/orch01-real.db",
        connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    seed = session_factory()
    seed.add(Tenant(id="tenant-real", name="Tenant Real",
                    subdomain="tenant-real"))
    seed.add(Workspace(id="ws-real", name="Workspace Real",
                       tenant_id="tenant-real"))
    seed.add(User(
        id=APPROVER_ID, tenant_id="tenant-real", workspace_id="ws-real",
        email="approver@example.com", hashed_password="x",
        first_name="A", last_name="One", role="member", status="active",
        is_active=True))
    seed.commit()
    seed.close()

    import core.database as database
    monkeypatch.setattr(database, "SessionLocal", session_factory)
    return {"engine": engine, "Session": session_factory}


@pytest.fixture()
def governance_pending(monkeypatch):
    from core.agent_governance_service import AgentGovernanceService

    monkeypatch.setattr(
        AgentGovernanceService, "__init__", lambda self, db: None)
    monkeypatch.setattr(
        AgentGovernanceService, "enforce_action",
        lambda *args, **kwargs: {
            "proceed": True,
            "status": "PENDING_APPROVAL",
            "action_required": "WAIT_FOR_APPROVAL",
        })


def _compiled():
    return compile_blueprint(
        {
            "architecture_name": "Controlled record write",
            "description": "Write one reviewed record.",
            "execution_mode": "one_off",
            "nodes": [{
                "id": "record",
                "type": "entity",
                "name": "Write record",
                "action": {"kind": "write"},
                "metadata": {
                    "entity_name": "controlled record",
                    "entity_type": "business_record",
                },
            }],
        },
        execution_mode="one_off",
        workspace_id=SCOPE["workspace_id"],
        tenant_id=SCOPE["tenant_id"],
    )


def _definition(compiled):
    steps = [
        WorkflowStep(
            step_id=raw["step_id"],
            step_type=WorkflowStepType(raw["step_type"]),
            description=raw["description"],
            parameters=dict(raw["parameters"]),
            next_steps=list(raw["next_steps"]),
        )
        for raw in compiled["steps"]
    ]
    return WorkflowDefinition(
        workflow_id=compiled["workflow_id"],
        name=compiled["name"],
        description=compiled["description"],
        steps=steps,
        start_step=compiled["start_step"],
        definition_digest=compiled["definition_digest"],
    )


def _orchestrator(compiled, effects, *, extra_definitions=()):
    orch = AdvancedWorkflowOrchestrator.__new__(
        AdvancedWorkflowOrchestrator)
    orch.workflows = {}
    for definition in extra_definitions:
        orch.workflows[definition.workflow_id] = definition
    definition = _definition(compiled)
    orch.workflows[definition.workflow_id] = definition
    orch.active_contexts = {}
    orch.ai_service = None
    orch.http_sessions = {}
    orch.template_manager = None
    orch.memory_snapshots = {}

    async def conditions(*args, **kwargs):
        return True

    async def dispatch(workflow, current_step, context):
        if current_step.step_type == WorkflowStepType.APPROVAL_REQUIRED:
            return await orch._execute_approval_required_step(
                current_step, context)
        effects.append(current_step.step_id)
        return {"status": "completed"}

    orch._check_conditions = conditions
    orch._execute_step_by_type = dispatch
    orch._create_snapshot = lambda *args, **kwargs: None
    return orch, definition


def _approval_step(compiled):
    return next(
        step for step in compiled["steps"]
        if step["step_type"] == "approval_required")


def _execute(orch, definition, execution_id, input_data):
    return asyncio.run(orch.execute_workflow(
        definition.workflow_id,
        input_data,
        execution_context={**SCOPE, "user_id": APPROVER_ID},
        execution_id=execution_id,
    ))


def _rows(real_db):
    db = real_db["Session"]()
    try:
        return db.query(HITLAction).all()
    finally:
        db.close()


def _row_for_execution(real_db, execution_id):
    return next(
        row for row in _rows(real_db)
        if (row.params or {}).get("workflow_id") == execution_id)


def test_pending_resume_refuses_then_exact_approval_releases_once(
        real_db, governance_pending):
    compiled = _compiled()
    approval_step = _approval_step(compiled)
    execution_id = "exec-real-approve"
    effects = []
    orch, definition = _orchestrator(compiled, effects)

    context = _execute(orch, definition, execution_id, {"amount": 100})
    assert context.status == WorkflowStatus.WAITING_APPROVAL
    assert effects == []

    rows = _rows(real_db)
    assert len(rows) == 1
    row = rows[0]
    assert row.status == "pending"
    assert row.params["workflow_id"] == execution_id
    assert row.params["definition_id"] == compiled["workflow_id"]
    assert row.params["step_id"] == approval_step["step_id"]
    assert row.params["guarded_step"] == "record"
    assert row.params["guarded_digest"]
    assert row.params["input_digest"]
    assert row.params["workspace_id"] == SCOPE["workspace_id"]
    assert row.params["tenant_id"] == SCOPE["tenant_id"]

    # A pending review never releases the branch, even from a fresh
    # orchestrator whose only memory is the persisted execution.
    pending_orch, _ = _orchestrator(compiled, effects)
    resumed = asyncio.run(pending_orch.resume_workflow(
        execution_id, approval_step["step_id"]))
    assert effects == []
    assert resumed.status == WorkflowStatus.WAITING_APPROVAL

    from core.intervention_service import intervention_service
    approved = asyncio.run(intervention_service.approve_intervention(
        row.id, APPROVER_ID))
    assert approved["success"] is True

    # The decoy workflow contains the same step id but a different guarded
    # effect. Execution identity must resolve the original definition.
    decoy = WorkflowDefinition(
        workflow_id="decoy-workflow",
        name="Decoy",
        description="",
        steps=[
            WorkflowStep(
                step_id=approval_step["step_id"],
                step_type=WorkflowStepType.APPROVAL_REQUIRED,
                description="Decoy approval",
                parameters={
                    "action": "workflow_step",
                    "server_required": True,
                    "workflow_id": "decoy-workflow",
                    "guarded_step": "decoy-effect",
                },
                next_steps=["decoy-effect"],
            ),
            WorkflowStep(
                step_id="decoy-effect",
                step_type=WorkflowStepType.ENTITY,
                description="Decoy effect",
                parameters={"action": "create"},
            ),
        ],
        start_step=approval_step["step_id"],
    )
    approved_orch, _ = _orchestrator(
        compiled, effects, extra_definitions=[decoy])
    # Put the decoy first: scan-by-step-id would pick it.
    approved_orch.workflows = {
        decoy.workflow_id: decoy,
        **approved_orch.workflows,
    }
    resumed = asyncio.run(approved_orch.resume_workflow(
        execution_id, approval_step["step_id"]))
    assert effects == ["record"]
    assert resumed.status == WorkflowStatus.COMPLETED

    # Duplicate continuation must not repeat the governed effect.
    duplicate_orch, _ = _orchestrator(compiled, effects)
    asyncio.run(duplicate_orch.resume_workflow(
        execution_id, approval_step["step_id"]))
    assert effects == ["record"]


def test_rejected_checkpoint_and_missing_checkpoint_dispatch_nothing(
        real_db, governance_pending):
    compiled = _compiled()
    approval_step = _approval_step(compiled)

    rejected_id = "exec-real-rejected"
    effects = []
    orch, definition = _orchestrator(compiled, effects)
    _execute(orch, definition, rejected_id, {"amount": 10})
    rejected_row = _row_for_execution(real_db, rejected_id)

    from core.intervention_service import intervention_service
    rejected = asyncio.run(intervention_service.reject_intervention(
        rejected_row.id, APPROVER_ID, "not approved"))
    assert rejected["success"] is True

    rejected_orch, _ = _orchestrator(compiled, effects)
    resumed = asyncio.run(rejected_orch.resume_workflow(
        rejected_id, approval_step["step_id"]))
    assert effects == []
    assert resumed.status == WorkflowStatus.FAILED
    assert resumed.results[approval_step["step_id"]]["status"] == "rejected"

    # A missing durable row must not create a fresh review or release work.
    missing_id = "exec-real-missing"
    missing_orch, missing_definition = _orchestrator(compiled, effects)
    _execute(missing_orch, missing_definition, missing_id, {"amount": 20})
    missing_row = _row_for_execution(real_db, missing_id)
    db = real_db["Session"]()
    try:
        db.delete(db.query(HITLAction).filter(
            HITLAction.id == missing_row.id).one())
        db.commit()
    finally:
        db.close()
    assert all(
        (row.params or {}).get("workflow_id") != missing_id
        for row in _rows(real_db))

    missing_resume_orch, _ = _orchestrator(compiled, effects)
    resumed = asyncio.run(missing_resume_orch.resume_workflow(
        missing_id, approval_step["step_id"]))
    assert effects == []
    assert resumed.status == WorkflowStatus.FAILED
    assert resumed.results[approval_step["step_id"]]["status"] == (
        "unavailable")
    assert all(
        (row.params or {}).get("workflow_id") != missing_id
        for row in _rows(real_db))


def test_changed_reviewed_material_cannot_reuse_old_approval(
        real_db, governance_pending):
    compiled = _compiled()
    approval_step = _approval_step(compiled)
    execution_id = "exec-real-changed"
    effects = []
    orch, definition = _orchestrator(compiled, effects)
    _execute(orch, definition, execution_id, {"amount": 100})
    row = _row_for_execution(real_db, execution_id)

    from core.intervention_service import intervention_service
    approved = asyncio.run(intervention_service.approve_intervention(
        row.id, APPROVER_ID))
    assert approved["success"] is True

    # The reviewed input changes after approval. The old receipt must not
    # match the new execution material.
    db = real_db["Session"]()
    try:
        persisted = db.query(WorkflowExecution).filter(
            WorkflowExecution.execution_id == execution_id).one()
        persisted.input_data = json.dumps({"amount": 999})
        db.commit()
    finally:
        db.close()

    changed_orch, _ = _orchestrator(compiled, effects)
    resumed = asyncio.run(changed_orch.resume_workflow(
        execution_id, approval_step["step_id"]))
    assert effects == []
    assert resumed.status == WorkflowStatus.FAILED
    assert resumed.results[approval_step["step_id"]]["status"] == (
        "unavailable")


def test_public_approval_route_requires_scope_and_exact_binding(
        real_db, governance_pending, monkeypatch):
    from fastapi import HTTPException

    from integrations import workflow_approval_routes as routes

    compiled = _compiled()
    approval_step = _approval_step(compiled)
    first_id = "exec-route-first"
    second_id = "exec-route-second"
    effects = []
    orch, definition = _orchestrator(compiled, effects)
    _execute(orch, definition, first_id, {"amount": 1})
    _execute(orch, definition, second_id, {"amount": 2})
    first_row = _row_for_execution(real_db, first_id)
    second_row = _row_for_execution(real_db, second_id)

    route_orch, _ = _orchestrator(compiled, effects)

    def get_route_orchestrator():
        return route_orch

    monkeypatch.setattr(
        "advanced_workflow_orchestrator.get_orchestrator",
        get_route_orchestrator)

    # Tamper the first execution's cached result so it points at the second
    # execution's approval. The binding check must refuse before any decision.
    db = real_db["Session"]()
    try:
        persisted = db.query(WorkflowExecution).filter(
            WorkflowExecution.execution_id == first_id).one()
        state = json.loads(persisted.context)
        state["results"][approval_step["step_id"]]["hitl_action_id"] = (
            second_row.id)
        persisted.context = json.dumps(state)
        db.commit()
    finally:
        db.close()

    user = SimpleNamespace(
        id=APPROVER_ID, workspace_id=SCOPE["workspace_id"],
        tenant_id=SCOPE["tenant_id"])
    route_db = real_db["Session"]()
    try:
        with pytest.raises(HTTPException) as mismatch:
            asyncio.run(routes.respond_to_approval(
                first_id,
                routes.ApprovalResponse(
                    decision="approve",
                    step_id=approval_step["step_id"]),
                db=route_db,
                user=user,
            ))
        assert mismatch.value.status_code == 409
        assert effects == []

        # An out-of-scope approver cannot even see the bound row.
        outsider = SimpleNamespace(
            id="approver-2", workspace_id="ws-other",
            tenant_id="tenant-real")
        with pytest.raises(HTTPException) as denied:
            asyncio.run(routes.respond_to_approval(
                first_id,
                routes.ApprovalResponse(
                    decision="approve",
                    step_id=approval_step["step_id"]),
                db=route_db,
                user=outsider,
            ))
        assert denied.value.status_code == 404
        assert effects == []

        # Restore the exact binding; the public approve surface consumes the
        # real row and resumes through the same checkpoint consumer.
        state["results"][approval_step["step_id"]]["hitl_action_id"] = (
            first_row.id)
        persisted = route_db.query(WorkflowExecution).filter(
            WorkflowExecution.execution_id == first_id).one()
        persisted.context = json.dumps(state)
        route_db.commit()
        # Reload so respond_to_approval sees the restored context.
        route_db.expire_all()

        response = asyncio.run(routes.respond_to_approval(
            first_id,
            routes.ApprovalResponse(
                decision="approve", step_id=approval_step["step_id"]),
            db=route_db,
            user=user,
        ))
        assert response["status"] == "success"
        assert effects == ["record"]

        route_db.expire_all()
        with pytest.raises(HTTPException) as replay:
            asyncio.run(routes.respond_to_approval(
                first_id,
                routes.ApprovalResponse(
                    decision="approve", step_id=approval_step["step_id"]),
                db=route_db,
                user=user,
            ))
        assert replay.value.status_code == 400
        assert effects == ["record"]
    finally:
        route_db.close()
