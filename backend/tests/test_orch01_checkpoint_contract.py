"""ORCH-01 compiler authority and real checkpoint-consumer contracts."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from advanced_workflow_orchestrator import (
    AdvancedWorkflowOrchestrator,
    WorkflowContext,
    WorkflowDefinition,
    WorkflowStep,
    WorkflowStepType,
)
from core.agents.workflow_blueprint import (
    BlueprintValidationError,
    compile_blueprint,
)


def _compile(nodes, *, mode="one_off"):
    return compile_blueprint(
        {"architecture_name": "checkpoint control", "execution_mode": mode,
         "nodes": nodes},
        execution_mode=mode, workspace_id="ws-1", tenant_id="tenant-1")


def _steps(compiled):
    return [
        WorkflowStep(
            step_id=raw["step_id"],
            step_type=WorkflowStepType(raw["step_type"]),
            description=raw["description"],
            parameters=raw["parameters"],
            next_steps=raw["next_steps"])
        for raw in compiled["steps"]
    ]


def _orchestrator(monkeypatch, *, enforce, approval_row=None,
                  created_id="hitl-created"):
    from core import agent_governance_service as governance
    import core.database as database

    @contextmanager
    def scratch_session():
        yield SimpleNamespace()

    monkeypatch.setattr(database, "get_db_session", scratch_session)
    monkeypatch.setattr(
        governance.AgentGovernanceService, "__init__",
        lambda self, db: None)
    monkeypatch.setattr(
        governance.AgentGovernanceService, "enforce_action",
        lambda *args, **kwargs: enforce)

    orch = AdvancedWorkflowOrchestrator.__new__(AdvancedWorkflowOrchestrator)
    orch._check_conditions = lambda *args, **kwargs: _true()
    orch._create_snapshot = lambda *args, **kwargs: None

    async def _find(_material):
        return approval_row

    async def _create(_material, _step, _context):
        return created_id

    monkeypatch.setattr(orch, "_find_durable_approval", _find)
    monkeypatch.setattr(orch, "_create_durable_approval", _create)
    return orch


async def _true():
    return True


def _run(orch, compiled, effects, context=None):
    async def dispatch(workflow, current_step, ctx):
        if current_step.step_type == WorkflowStepType.APPROVAL_REQUIRED:
            return await orch._execute_approval_required_step(
                current_step, ctx)
        effects.append(current_step.step_id)
        return {"status": "completed"}

    orch._execute_step_by_type = dispatch
    definition = WorkflowDefinition(
        workflow_id=compiled["workflow_id"],
        name=compiled["name"],
        description="",
        steps=_steps(compiled),
        start_step=compiled["start_step"],
    )
    if context is None:
        context = WorkflowContext(workflow_id=definition.workflow_id)
    asyncio.run(orch._execute_workflow_step(
        definition, definition.start_step, context))
    return context


def test_pending_governance_blocks_descendants(monkeypatch):
    compiled = _compile([{
        "id": "write", "type": "entity", "name": "Write",
        "action": {"kind": "write"},
        "metadata": {"entity_name": "record", "entity_type": "record"},
    }])
    orch = _orchestrator(monkeypatch, enforce={
        "proceed": True, "status": "PENDING_APPROVAL",
        "action_required": "WAIT_FOR_APPROVAL"})
    effects = []
    context = _run(orch, compiled, effects)
    assert effects == []
    approval = next(
        step for step in compiled["steps"]
        if step["step_type"] == "approval_required")
    assert context.results[approval["step_id"]]["status"] == "waiting_approval"


def test_blocked_governance_blocks_descendants(monkeypatch):
    compiled = _compile([{
        "id": "write", "type": "entity", "name": "Write",
        "action": {"kind": "write"},
        "metadata": {"entity_name": "record", "entity_type": "record"},
    }])
    orch = _orchestrator(monkeypatch, enforce={
        "proceed": False, "status": "BLOCKED", "reason": "denied"})
    effects = []
    context = _run(orch, compiled, effects)
    assert effects == []
    assert context.status.value == "failed"


def test_mature_agent_cannot_waive_server_checkpoint(monkeypatch):
    compiled = _compile([{
        "id": "write", "type": "entity", "name": "Write",
        "action": {"kind": "write"},
        "metadata": {"entity_name": "record", "entity_type": "record"},
    }])
    orch = _orchestrator(
        monkeypatch, enforce={"proceed": True, "status": "APPROVED"},
        approval_row=None, created_id="hitl-required")
    effects = []
    context = _run(orch, compiled, effects)
    assert effects == []
    approval = next(
        step for step in compiled["steps"]
        if step["step_type"] == "approval_required")
    result = context.results[approval["step_id"]]
    assert result["status"] == "waiting_approval"
    assert result["hitl_action_id"] == "hitl-required"


def test_rejected_durable_approval_blocks_descendants(monkeypatch):
    compiled = _compile([{
        "id": "write", "type": "entity", "name": "Write",
        "action": {"kind": "write"},
        "metadata": {"entity_name": "record", "entity_type": "record"},
    }])
    rejected = SimpleNamespace(status="rejected", id="hitl-rejected")
    orch = _orchestrator(monkeypatch, enforce={
        "proceed": True, "status": "PENDING_APPROVAL",
        "action_required": "WAIT_FOR_APPROVAL"}, approval_row=rejected)
    effects = []
    context = _run(orch, compiled, effects)
    assert effects == []
    approval = next(
        step for step in compiled["steps"]
        if step["step_type"] == "approval_required")
    assert context.results[approval["step_id"]]["status"] == "rejected"


def test_valid_approval_dispatches_exactly_one_effect(monkeypatch):
    compiled = _compile([{
        "id": "write", "type": "entity", "name": "Write",
        "action": {"kind": "write"},
        "metadata": {"entity_name": "record", "entity_type": "record"},
    }])
    approved = SimpleNamespace(status="approved", id="hitl-approved")
    orch = _orchestrator(monkeypatch, enforce={
        "proceed": True, "status": "APPROVED"}, approval_row=approved)
    effects = []
    context = _run(orch, compiled, effects)
    assert effects == ["write"], effects
    # A duplicate continuation from the same start must not re-dispatch the
    # downstream governed effect.
    _run(orch, compiled, effects, context=context)
    assert effects == ["write"], effects


def test_entity_read_label_cannot_inject_metadata_create(monkeypatch):
    compiled = _compile([{
        "id": "read", "type": "entity", "name": "Read",
        "action": {"kind": "read"},
        "metadata": {"action": "create", "entity_name": "record",
                     "entity_type": "record"},
    }])
    assert compiled["hitl_gates"] == []
    step = next(
        raw for raw in compiled["steps"] if raw["step_id"] == "read")
    assert step["parameters"]["action"] == "lookup"

    import core.graphrag_engine as ge
    calls = []

    class Engine:
        def __init__(self, **kwargs):
            pass

        def add_entity(self, entity):
            calls.append(entity)
            return "created"

        def canonical_search(self, **kwargs):
            return []

    monkeypatch.setattr(ge, "GraphRAGEngine", Engine)
    orch = AdvancedWorkflowOrchestrator.__new__(AdvancedWorkflowOrchestrator)
    outcome = asyncio.run(orch._execute_entity_node(
        WorkflowStep(
            step_id="read", step_type=WorkflowStepType.ENTITY,
            description="Read", parameters=step["parameters"]),
        SimpleNamespace(variables={"workspace_id": "ws-1"})))
    assert calls == []
    assert outcome["status"] == "completed"


def test_unknown_action_reference_is_refused():
    with pytest.raises(BlueprintValidationError) as exc:
        _compile([{
            "id": "x", "type": "skill", "name": "Unknown",
            "action": {"kind": "read",
                       "service": "not_a_registered_service",
                       "action": "not_a_registered_action"},
        }])
    assert exc.value.code == "workflow_action_reference_unknown"


def test_unbound_capability_is_non_executable_not_registered(monkeypatch):
    compiled = _compile([{
        "id": "x", "type": "skill", "name": "Unbound",
        "capability_required": "not_a_known_business_agent",
        "action": {"kind": "read"},
    }])
    assert compiled["execution_ready"] is False
    assert compiled["execution_blockers"]
    import core.workflow_blueprint_service as service

    registered = []
    monkeypatch.setattr(
        "advanced_workflow_orchestrator.get_orchestrator",
        lambda: SimpleNamespace(
            register_workflow=lambda definition: registered.append(definition)))
    assert service.register_compiled_workflow(compiled) is False
    assert registered == []


def test_unsupported_entity_operation_is_non_executable_not_rewritten():
    compiled = _compile([{
        "id": "record", "type": "entity", "name": "Delete existing record",
        "action": {"kind": "write", "service": "knowledge",
                   "action": "delete"},
        "metadata": {"entity_name": "existing record",
                     "entity_type": "business_record"},
    }])
    assert compiled["execution_ready"] is False
    step = next(raw for raw in compiled["steps"]
                if raw["step_id"] == "record")
    # The declared operation is preserved; it is never silently changed to
    # create. The design is simply not executable.
    assert step["parameters"]["action"] == "delete"
    assert any("delete" in blocker
               for blocker in compiled["execution_blockers"])


@pytest.mark.parametrize(
    "operation,kind",
    [("create", "write"), ("update", "write"),
     ("query", "read"), ("lookup", "read")],
)
def test_supported_entity_operations_are_preserved(operation, kind):
    compiled = _compile([{
        "id": "record", "type": "entity", "name": "Entity operation",
        "action": {"kind": kind, "service": "knowledge",
                   "action": operation},
        "metadata": {"entity_name": "record", "entity_type": "record"},
    }])
    assert compiled["execution_ready"] is True
    step = next(raw for raw in compiled["steps"]
                if raw["step_id"] == "record")
    assert step["parameters"]["action"] == operation


def test_declared_entity_read_label_is_not_silently_aliased():
    compiled = _compile([{
        "id": "record", "type": "entity", "name": "Read entity",
        "action": {"kind": "read", "service": "knowledge",
                   "action": "read"},
        "metadata": {"entity_name": "record", "entity_type": "record"},
    }])
    assert compiled["execution_ready"] is False
    step = next(raw for raw in compiled["steps"]
                if raw["step_id"] == "record")
    assert step["parameters"]["action"] == "read"
    assert compiled["execution_blockers"]


def test_skill_action_must_exist_in_the_real_action_registry():
    compiled = _compile([{
        "id": "skill", "type": "skill", "name": "Delete knowledge",
        "capability_required": "accounting",
        "action": {"kind": "write", "service": "knowledge",
                   "action": "delete"},
    }])
    assert compiled["execution_ready"] is False
    assert any("knowledge.delete" in blocker
               for blocker in compiled["execution_blockers"])

    supported = _compile([{
        "id": "skill", "type": "skill", "name": "Query knowledge",
        "capability_required": "accounting",
        "action": {"kind": "read", "service": "knowledge",
                   "action": "query"},
    }])
    assert supported["execution_ready"] is True
    assert supported["execution_blockers"] == []


def test_full_execution_completes_after_successful_required_work():
    compiled = _compile([{
        "id": "read", "type": "entity", "name": "Read record",
        "action": {"kind": "read"},
        "metadata": {"entity_name": "record", "entity_type": "record"},
    }])
    orch = AdvancedWorkflowOrchestrator.__new__(AdvancedWorkflowOrchestrator)
    effects = []

    async def conditions(*args, **kwargs):
        return True

    async def dispatch(workflow, step, context):
        effects.append(step.step_id)
        return {"status": "completed"}

    orch._check_conditions = conditions
    orch._execute_step_by_type = dispatch
    orch._create_snapshot = lambda *args, **kwargs: None
    definition = WorkflowDefinition(
        workflow_id=compiled["workflow_id"],
        name=compiled["name"],
        description="",
        steps=_steps(compiled),
        start_step=compiled["start_step"],
    )
    orch.workflows = {definition.workflow_id: definition}
    orch.active_contexts = {}
    orch.ai_service = None
    orch._save_execution_state = lambda *args, **kwargs: None

    context = asyncio.run(orch.execute_workflow(
        definition.workflow_id, {"workspace_id": "ws-1"}))
    assert context.status.value == "completed"
    assert effects == ["read"]
