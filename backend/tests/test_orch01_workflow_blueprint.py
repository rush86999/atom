"""ORCH-01 — plain-language request -> validated blueprint -> durable readback.

The model transport is doubled. These controls use the real route, compiler,
SQLite persistence and read path; no provider/network call occurs.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from advanced_workflow_api import router
from core.agents.workflow_blueprint import (
    BlueprintValidationError,
    WorkflowBlueprintDraft,
    compile_blueprint,
)
from core.auth import get_current_user as auth_get_current_user
from core.database import Base, get_db
from core.models import Tenant, User, Workflow, WorkflowStep
from core.security_dependencies import get_current_user as security_get_current_user


def _draft(
    *, name="Vendor invoice intake and review",
    mode="one_off", nodes=None, missing=None,
):
    return {
        "architecture_name": name,
        "description": "A reusable review workflow.",
        "execution_mode": mode,
        "nodes": nodes or [
            {"id": "intake", "type": "agent", "name": "Intake request",
             "action": {"kind": "read"}},
            {"id": "triage", "type": "agent", "name": "Triage request",
             "dependencies": ["intake"], "action": {"kind": "compute"}},
            {"id": "notify", "type": "agent", "name": "Notify reviewer",
             "dependencies": ["triage"],
             "action": {"kind": "notify", "service": "email",
                        "action": "send"}},
            {"id": "record", "type": "entity", "name": "Record review",
             "dependencies": ["notify"], "action": {"kind": "write"}},
        ],
        "required_integrations": [],
        "missing_capabilities": missing or [],
    }


def _inventory_draft():
    return _draft(
        name="Weekly inventory review",
        mode="recurring_automation",
        nodes=[
            {"id": "weekly", "type": "trigger", "name": "Weekly schedule",
             "metadata": {"schedule": "0 8 * * 1"}},
            {"id": "collect", "type": "agent", "name": "Collect counts",
             "dependencies": ["weekly"], "action": {"kind": "read"}},
            {"id": "compare", "type": "agent", "name": "Compare thresholds",
             "dependencies": ["collect"], "action": {"kind": "compute"}},
            {"id": "stock", "type": "entity", "name": "Update stock review",
             "dependencies": ["compare"], "action": {"kind": "write"}},
        ])


class FakeOrchestrator:
    def __init__(self):
        self.registered = []
        self.executed = []

    def register_workflow(self, definition):
        self.registered.append(definition)
        return definition.workflow_id

    async def execute_workflow(self, *args, **kwargs):
        self.executed.append((args, kwargs))
        raise AssertionError("blueprint generation must not execute")


@pytest.fixture()
def orch_env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path}/orch01.db",
        connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    db.add(Tenant(id="tenant-1", name="Tenant One", subdomain="tenant-one"))
    db.add(User(
        id="user-1", email="user@example.com", hashed_password="x",
        first_name="U", last_name="One", role="member", status="active",
        workspace_id="ws-1", tenant_id="tenant-1", is_active=True))
    db.add(User(
        id="user-2", email="other@example.com", hashed_password="x",
        first_name="O", last_name="Two", role="member", status="active",
        workspace_id="ws-2", tenant_id="tenant-1", is_active=True))
    db.commit()
    user = SimpleNamespace(
        id="user-1", tenant_id="tenant-1", workspace_id="ws-1",
        role="member")
    other_workspace = SimpleNamespace(
        id="user-2", tenant_id="tenant-1", workspace_id="ws-2",
        role="member")
    other_tenant = SimpleNamespace(
        id="user-3", tenant_id="tenant-2", workspace_id="ws-1",
        role="member")
    fake = FakeOrchestrator()
    monkeypatch.setattr(
        "advanced_workflow_orchestrator.get_orchestrator", lambda: fake)
    return {
        "engine": engine, "Session": Session, "db": db, "user": user,
        "other_workspace": other_workspace, "other_tenant": other_tenant,
        "fake": fake,
    }


def _client(db, user):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[auth_get_current_user] = lambda: user
    app.dependency_overrides[security_get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def _configure_model(monkeypatch, state):
    async def fake_structured(self, **kwargs):
        state["calls"].append(kwargs)
        draft = state.get("draft")
        if isinstance(draft, BaseException):
            raise draft
        if draft is None:
            return None
        return kwargs["response_model"].model_validate(draft)

    monkeypatch.setattr(
        "core.llm_service.LLMService.generate_structured_response",
        fake_structured)

    async def classify(self, prompt, **_kwargs):
        from ai.nlp_engine import RouteCategory
        explicit_mode = state.get("mode")
        if explicit_mode:
            category = (
                RouteCategory.AUTOMATION
                if explicit_mode == "recurring_automation"
                else RouteCategory.ONE_OFF)
        else:
            category = (
                RouteCategory.AUTOMATION
                if "recurring" in prompt.lower()
                or "weekly" in prompt.lower()
                else RouteCategory.ONE_OFF)
        return SimpleNamespace(category=category, reasoning="controlled route")

    monkeypatch.setattr(
        "ai.nlp_engine.NaturalLanguageEngine.classify_route", classify)


def test_two_domains_validate_persist_and_read_back_exactly(
        orch_env, monkeypatch):
    state = {"calls": [], "draft": _draft()}
    _configure_model(monkeypatch, state)
    client = _client(orch_env["db"], orch_env["user"])

    first = client.post(
        "/api/v1/workflows/generate-from-agent",
        json={"prompt": "Review the service intake request"})
    assert first.status_code == 200, first.text
    created = first.json()
    assert created["workflow_id"].startswith("ai_wf_")
    assert created["status"] == "designed"
    assert created["definition_digest"]
    assert created["hitl_gates"]
    # The captured design has skill/agent steps whose capabilities are not
    # bound to a registered business agent: it is a reviewable design, not a
    # runnable workflow.
    assert created["execution_ready"] is False
    assert created["execution_blockers"]
    assert created["registration"]["registered"] is False
    assert len(state["calls"]) == 1
    assert state["calls"][0]["capability_profile"] == "workflow_blueprint"
    assert orch_env["fake"].registered == []
    assert orch_env["fake"].executed == []

    # A fresh session/app process reads the committed definition, not the
    # in-memory orchestrator.
    orch_env["fake"].registered.clear()
    fresh_db = orch_env["Session"]()
    fresh = _client(fresh_db, orch_env["user"]).get(
        f"/api/v1/workflows/generated/{created['workflow_id']}")
    assert fresh.status_code == 200, fresh.text
    readback = fresh.json()
    assert readback["definition_digest"] == created["definition_digest"]
    assert readback["nodes"] == created["nodes"]
    assert readback["steps"] == created["steps"]
    assert readback["start_step"] == created["start_step"]
    assert readback["triggers"] == created["triggers"]
    fresh_db.close()

    # Second domain on the same implementation.
    state["draft"] = _inventory_draft()
    second = client.post(
        "/api/v1/workflows/generate-from-agent",
        json={"prompt": "Build a recurring weekly inventory review"})
    assert second.status_code == 200, second.text
    inventory = second.json()
    assert inventory["execution_mode"] == "recurring_automation"
    assert inventory["triggers"]
    assert inventory["execution_ready"] is False
    assert inventory["execution_blockers"]
    assert inventory["registration"]["registered"] is False
    assert orch_env["fake"].registered == []
    assert orch_env["fake"].executed == []
    assert len(state["calls"]) == 2

    # Durable rows and exact scope.
    db = orch_env["db"]
    row = db.query(Workflow).filter(
        Workflow.id == inventory["workflow_id"]).one()
    assert row.tenant_id == "tenant-1"
    assert row.status == "designed"
    assert row.configuration["workspace_id"] == "ws-1"
    assert db.query(WorkflowStep).filter(
        WorkflowStep.workflow_id == row.id).count() == len(
            inventory["steps"])


def test_execution_ready_entity_design_registers_for_manual_execution(
        orch_env, monkeypatch):
    draft = _draft(name="Controlled record review", nodes=[
        {"id": "record", "type": "entity", "name": "Review record",
         "action": {"kind": "write"},
         "metadata": {"entity_name": "review", "entity_type": "record"}},
    ])
    state = {"calls": [], "draft": draft}
    _configure_model(monkeypatch, state)
    client = _client(orch_env["db"], orch_env["user"])
    response = client.post(
        "/api/v1/workflows/generate-from-agent",
        json={"prompt": "Review one controlled record"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["execution_ready"] is True
    assert body["execution_blockers"] == []
    assert body["registration"]["registered"] is True
    assert len(orch_env["fake"].registered) == 1
    registered = orch_env["fake"].registered[0]
    assert registered.triggers == []
    assert registered.start_step == body["start_step"]
    types = [step.step_type.value for step in registered.steps]
    assert "approval_required" in types
    assert "entity" in types
    assert "universal_integration" not in types
    assert orch_env["fake"].executed == []


def test_route_persisted_definition_stops_at_checkpoint_consumer(
        orch_env, monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace

    from advanced_workflow_orchestrator import (
        AdvancedWorkflowOrchestrator, WorkflowContext, WorkflowDefinition,
        WorkflowStep, WorkflowStepType,
    )

    draft = _draft(name="Controlled record review", nodes=[
        {"id": "record", "type": "entity", "name": "Review record",
         "action": {"kind": "write"},
         "metadata": {"entity_name": "review", "entity_type": "record"}},
    ])
    state = {"calls": [], "draft": draft}
    _configure_model(monkeypatch, state)
    client = _client(orch_env["db"], orch_env["user"])
    response = client.post(
        "/api/v1/workflows/generate-from-agent",
        json={"prompt": "Review one controlled record"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["execution_ready"] is True
    assert body["registration"]["registered"] is True

    import core.database as database
    import core.agent_governance_service as governance

    @contextmanager
    def scratch_session():
        yield SimpleNamespace()

    monkeypatch.setattr(database, "get_db_session", scratch_session)
    monkeypatch.setattr(
        governance.AgentGovernanceService, "__init__",
        lambda self, db: None)
    monkeypatch.setattr(
        governance.AgentGovernanceService, "enforce_action",
        lambda *args, **kwargs: {
            "proceed": True, "status": "PENDING_APPROVAL",
            "action_required": "WAIT_FOR_APPROVAL"})

    effects = []
    orch = AdvancedWorkflowOrchestrator.__new__(AdvancedWorkflowOrchestrator)

    async def checkpoint_row(_material):
        return SimpleNamespace(status="pending", id="hitl-route-control")

    async def create_checkpoint(_material, _step, _context):
        return "hitl-route-control"

    # This control exercises the route -> persisted definition -> consumer
    # wiring with a controlled durable seam. Real HITLAction rows and fresh
    # sessions are covered by test_orch01_resume_durable.py.
    monkeypatch.setattr(orch, "_find_durable_approval", checkpoint_row)
    monkeypatch.setattr(orch, "_create_durable_approval", create_checkpoint)

    async def conditions(*args, **kwargs):
        return True
    async def dispatch(workflow, current_step, ctx):
        if current_step.step_type == WorkflowStepType.APPROVAL_REQUIRED:
            return await orch._execute_approval_required_step(
                current_step, ctx)
        effects.append(current_step.step_id)
        return {"status": "completed"}
    orch._check_conditions = conditions
    orch._execute_step_by_type = dispatch
    orch._create_snapshot = lambda *args, **kwargs: None
    steps = [
        WorkflowStep(
            step_id=raw["step_id"],
            step_type=WorkflowStepType(raw["step_type"]),
            description=raw["description"],
            parameters=raw["parameters"],
            next_steps=raw["next_steps"])
        for raw in body["steps"]
    ]
    definition = WorkflowDefinition(
        workflow_id=body["workflow_id"], name=body["name"],
        description=body["description"], steps=steps,
        start_step=body["start_step"])
    context = WorkflowContext(workflow_id=definition.workflow_id)
    asyncio.run(orch._execute_workflow_step(
        definition, definition.start_step, context))

    assert effects == []
    approval = next(
        step for step in steps
        if step.step_type == WorkflowStepType.APPROVAL_REQUIRED)
    assert context.results[approval.step_id]["status"] == "waiting_approval"


def test_hitl_gate_is_inserted_before_mutating_steps(orch_env, monkeypatch):
    state = {"calls": [], "draft": _draft()}
    _configure_model(monkeypatch, state)
    client = _client(orch_env["db"], orch_env["user"])
    response = client.post(
        "/api/v1/workflows/generate-from-agent",
        json={"prompt": "Review the service intake request"})
    assert response.status_code == 200, response.text
    body = response.json()
    nodes = body["nodes"]
    ids = [node["id"] for node in nodes]
    for guarded in ("notify", "record"):
        approval = f"approval_{guarded}"
        assert approval in ids
        assert ids.index(approval) < ids.index(guarded)
        guarded_node = next(node for node in nodes if node["id"] == guarded)
        assert approval in guarded_node["dependencies"]
    approval_steps = [
        step for step in body["steps"]
        if step["step_type"] == "approval_required"]
    assert len(approval_steps) == 2
    assert {step["step_id"] for step in approval_steps} == {
        "approval_notify", "approval_record"}


def test_forged_body_identity_is_ignored_and_read_scope_is_exact(
        orch_env, monkeypatch):
    state = {"calls": [], "draft": _draft()}
    _configure_model(monkeypatch, state)
    client = _client(orch_env["db"], orch_env["user"])
    response = client.post(
        "/api/v1/workflows/generate-from-agent",
        json={
            "prompt": "Review the service intake request",
            "tenant_id": "evil-tenant",
            "user_id": "evil-user",
        })
    assert response.status_code == 200, response.text
    workflow_id = response.json()["workflow_id"]
    assert state["calls"][0]["tenant_id"] == "tenant-1"
    assert state["calls"][0]["workspace_id"] == "ws-1"
    row = orch_env["db"].query(Workflow).filter(
        Workflow.id == workflow_id).one()
    assert row.tenant_id == "tenant-1"
    assert row.user_id == "user-1"

    foreign_ws = _client(
        orch_env["db"], orch_env["other_workspace"]).get(
            f"/api/v1/workflows/generated/{workflow_id}")
    assert foreign_ws.status_code == 404, foreign_ws.text
    foreign_tenant = _client(
        orch_env["db"], orch_env["other_tenant"]).get(
            f"/api/v1/workflows/generated/{workflow_id}")
    assert foreign_tenant.status_code == 404, foreign_tenant.text


@pytest.mark.parametrize("draft,expected_status,error_code", [
    ({"architecture_name": "x", "nodes": []}, 422,
     "workflow_blueprint_invalid"),
    ({"architecture_name": "x", "execution_mode": "one_off", "nodes": [
        {"id": "a", "type": "unknown", "name": "A"}]}, 422,
     "workflow_blueprint_invalid"),
    ({"architecture_name": "x", "execution_mode": "one_off", "nodes": [
        {"id": "a", "type": "agent", "name": "A",
         "action": {"kind": "delete"}}]}, 422,
     "workflow_blueprint_invalid"),
    ({"architecture_name": "x", "execution_mode": "one_off", "nodes": [
        {"id": "a", "type": "agent", "name": "A",
         "dependencies": ["missing"]}]}, 422,
     "workflow_dependency_missing"),
    ({"architecture_name": "x", "execution_mode": "one_off", "nodes": [
        {"id": "a", "type": "agent", "name": "A",
         "dependencies": ["b"]},
        {"id": "b", "type": "agent", "name": "B",
         "dependencies": ["a"]}]}, 422,
     "workflow_cycle"),
    ({"architecture_name": "x", "execution_mode": "one_off", "nodes": [
        {"id": "a", "type": "agent", "name": "A"},
        {"id": "b", "type": "agent", "name": "B"}]}, 422,
     "workflow_start_ambiguous"),
    ({"architecture_name": "x", "execution_mode": "recurring_automation",
      "nodes": [
          {"id": "a", "type": "agent", "name": "A"}]}, 422,
     "workflow_trigger_required"),
])
def test_invalid_route_drafts_are_refused_without_persistence(
        orch_env, monkeypatch, draft, expected_status, error_code):
    state = {
        "calls": [], "draft": draft,
        "mode": draft.get("execution_mode", "one_off"),
    }
    _configure_model(monkeypatch, state)
    client = _client(orch_env["db"], orch_env["user"])
    before = orch_env["db"].query(Workflow).count()
    response = client.post(
        "/api/v1/workflows/generate-from-agent",
        json={"prompt": "Build a workflow"})
    assert response.status_code == expected_status, response.text
    detail = response.json()["detail"]
    assert detail["error"] == error_code, detail
    assert orch_env["db"].query(Workflow).count() == before
    assert orch_env["fake"].registered == []
    assert len(state["calls"]) == 1


def test_missing_capability_is_a_safe_refusal_not_an_integration(
        orch_env, monkeypatch):
    draft = _draft(missing=[{"name": "payroll_adapter",
                             "description": "not installed"}])
    state = {"calls": [], "draft": draft}
    _configure_model(monkeypatch, state)
    client = _client(orch_env["db"], orch_env["user"])
    response = client.post(
        "/api/v1/workflows/generate-from-agent",
        json={"prompt": "Review the service intake request"})
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["error"] == "workflow_capability_missing"
    assert orch_env["fake"].registered == []


@pytest.mark.parametrize("failure,status,code", [
    (asyncio.TimeoutError(), 504, "workflow_blueprint_timeout"),
    (RuntimeError("provider down"), 503, "workflow_blueprint_unavailable"),
])
def test_model_failure_is_typed_and_creates_no_workflow(
        orch_env, monkeypatch, failure, status, code):
    state = {"calls": [], "draft": failure}
    _configure_model(monkeypatch, state)
    client = _client(orch_env["db"], orch_env["user"])
    before = orch_env["db"].query(Workflow).count()
    response = client.post(
        "/api/v1/workflows/generate-from-agent",
        json={"prompt": "Build a workflow"})
    assert response.status_code == status, response.text
    assert response.json()["detail"]["error"] == code
    assert orch_env["db"].query(Workflow).count() == before
    assert orch_env["fake"].registered == []


def test_empty_request_does_not_call_the_model(orch_env, monkeypatch):
    state = {"calls": [], "draft": _draft()}
    _configure_model(monkeypatch, state)
    client = _client(orch_env["db"], orch_env["user"])
    response = client.post(
        "/api/v1/workflows/generate-from-agent", json={"prompt": "   "})
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["error"] == "workflow_request_empty"
    assert state["calls"] == []


def test_compile_rejects_duplicate_ids_and_unknown_action():
    duplicate = _draft(nodes=[
        {"id": "a", "type": "agent", "name": "A"},
        {"id": "a", "type": "agent", "name": "B"},
    ])
    with pytest.raises(BlueprintValidationError) as exc:
        compile_blueprint(WorkflowBlueprintDraft.model_validate(duplicate))
    assert exc.value.code == "workflow_node_duplicate"

    unknown = _draft(nodes=[
        {"id": "a", "type": "agent", "name": "A",
         "action": {"kind": "destroy"}},
    ])
    with pytest.raises(Exception):
        WorkflowBlueprintDraft.model_validate(unknown)
