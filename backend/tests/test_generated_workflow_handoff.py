"""Generated workflow deployment/handoff contract tests.

Scratch-only: unique SQLite DB, unique JSON catalog, unique scheduler recorder.
The only doubled seam for generation is the model transport
(``LLMService.generate_structured_response``); compilation, persistence,
deployment, HITL rows and canonical execution are real.
"""
from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.agents.workflow_blueprint import WorkflowBlueprintDraft
from core.database import Base
from core.models import (
    AgentRegistry, HITLAction, Tenant, User, Workflow, Workspace,
)

TENANT_A = "tenant-a"
WS_A = "ws-a"
USER_A = "user-a"
REVIEWER_A = "reviewer-a"
AGENT_AUTO = "agent-auto"
AGENT_INTERN = "agent-intern"
TENANT_B = "tenant-b"
WS_B = "ws-b"
USER_B = "user-b"


def _draft_trigger() -> dict:
    return {
        "architecture_name": "Manual trigger design",
        "description": "One real compiled trigger step.",
        "execution_mode": "one_off",
        "nodes": [{
            "id": "start", "type": "trigger", "name": "Manual start",
            "metadata": {"trigger_event": "manual"},
        }],
        "required_integrations": [],
        "missing_capabilities": [],
    }


def _draft_recurring() -> dict:
    return {
        "architecture_name": "Recurring trigger design",
        "description": "Recurring design that must not auto-schedule.",
        "execution_mode": "recurring_automation",
        "nodes": [{
            "id": "start", "type": "trigger", "name": "Daily start",
            "metadata": {"schedule": "0 9 * * *"},
        }],
        "required_integrations": [],
        "missing_capabilities": [],
    }


def _draft_readonly() -> dict:
    return {
        "architecture_name": "Read-only record lookup",
        "description": "A real supported non-mutating entity lookup.",
        "execution_mode": "one_off",
        "nodes": [
            {
                "id": "start", "type": "trigger", "name": "Manual start",
                "metadata": {"trigger_event": "manual"},
            },
            {
                "id": "lookup", "type": "entity", "name": "Lookup record",
                "dependencies": ["start"],
                "action": {"kind": "read"},
                "metadata": {
                    "entity_name": "controlled record",
                    "entity_type": "business_record",
                },
            },
        ],
        "required_integrations": [],
        "missing_capabilities": [],
    }


def _draft_hitl() -> dict:
    return {
        "architecture_name": "Governed record write",
        "description": "A write that requires the server checkpoint.",
        "execution_mode": "one_off",
        "nodes": [
            {
                "id": "start", "type": "trigger", "name": "Manual start",
                "metadata": {"trigger_event": "manual"},
            },
            {
                "id": "record", "type": "entity", "name": "Write record",
                "dependencies": ["start"],
                "action": {"kind": "write"},
                "metadata": {
                    "entity_name": "controlled record",
                    "entity_type": "business_record",
                },
            },
        ],
        "required_integrations": [],
        "missing_capabilities": [],
    }


class _SchedulerRecorder:
    def __init__(self):
        self.calls = []

    def schedule_workflow(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return "job_scratch_1"

    def list_jobs(self):
        return [{"id": "job_scratch_1"}] if self.calls else []


@pytest.fixture()
def harness(tmp_path, monkeypatch):
    from core import database as database_module
    import core.intervention_service as intervention_module
    import advanced_workflow_orchestrator as orchestrator_module
    import core.security_dependencies as security_module
    import core.auth as auth_module
    from core.workflow_endpoints import router as workflow_router
    from advanced_workflow_api import router as advanced_router
    import core.workflow_endpoints as endpoints_module
    from core.llm_service import LLMService
    from ai.nlp_engine import RouteCategory, RouteClassification
    import ai.workflow_scheduler as scheduler_module

    engine = create_engine(
        f"sqlite:///{tmp_path}/handoff.db",
        connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def fresh_session():
        db = Session()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    monkeypatch.setattr(database_module, "SessionLocal", Session)
    monkeypatch.setattr(database_module, "get_db_session", fresh_session)
    monkeypatch.setattr(orchestrator_module, "get_db_session", fresh_session)
    monkeypatch.setattr(intervention_module, "get_db_session", fresh_session)

    seed = Session()
    for tenant, workspace in ((TENANT_A, WS_A), (TENANT_B, WS_B)):
        seed.add(Tenant(id=tenant, name=tenant, subdomain=tenant))
        seed.add(Workspace(id=workspace, name=workspace, tenant_id=tenant))
    seed.add(User(
        id=USER_A, tenant_id=TENANT_A, workspace_id=WS_A,
        email="a@example.invalid", hashed_password="x",
        first_name="A", last_name="User", role="super_admin",
        status="active", is_active=True))
    seed.add(User(
        id=REVIEWER_A, tenant_id=TENANT_A, workspace_id=WS_A,
        email="reviewer@example.invalid", hashed_password="x",
        first_name="R", last_name="Reviewer", role="team_lead",
        status="active", is_active=True))
    seed.add(User(
        id=USER_B, tenant_id=TENANT_B, workspace_id=WS_B,
        email="b@example.invalid", hashed_password="x",
        first_name="B", last_name="User", role="super_admin",
        status="active", is_active=True))
    seed.add(AgentRegistry(
        id=AGENT_AUTO, name="Autonomous agent", category="Operations",
        module_path="core.agents.queen_agent", class_name="QueenAgent",
        confidence_score=0.95, status="active", tenant_id=TENANT_A,
        workspace_id=WS_A, enabled=True, required_role_for_autonomy="team_lead"))
    seed.add(AgentRegistry(
        id=AGENT_INTERN, name="Intern agent", category="Operations",
        module_path="core.agents.queen_agent", class_name="QueenAgent",
        confidence_score=0.6, status="active", tenant_id=TENANT_A,
        workspace_id=WS_A, enabled=True, required_role_for_autonomy="team_lead"))
    seed.commit()
    seed.close()

    catalog = tmp_path / "workflows.json"
    catalog.write_text("[]\n")
    monkeypatch.setattr(endpoints_module, "WORKFLOWS_FILE", str(catalog))

    recorder = _SchedulerRecorder()
    monkeypatch.setattr(
        scheduler_module, "workflow_scheduler", recorder, raising=False)

    holder = {"user": Session().query(User).filter(User.id == USER_A).one()}

    app = FastAPI()
    app.include_router(workflow_router, prefix="/api/v1/workflows")
    app.include_router(advanced_router)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    async def override_user():
        return holder["user"]

    app.dependency_overrides[database_module.get_db] = override_db
    app.dependency_overrides[security_module.get_current_user] = override_user

    drafts = {"draft": _draft_trigger()}

    async def fake_structured_response(self, **kwargs):
        model = kwargs.get("response_model")
        if model is RouteClassification:
            recurring = "recurring" in str(kwargs.get("prompt") or "").lower()
            return RouteClassification(
                category=(RouteCategory.AUTOMATION if recurring
                          else RouteCategory.ONE_OFF),
                reasoning="scratch transport double", confidence=1.0)
        return WorkflowBlueprintDraft.model_validate(drafts["draft"])

    monkeypatch.setattr(
        LLMService, "generate_structured_response", fake_structured_response)

    yield SimpleNamespace(
        app=app, client=TestClient(app), Session=Session, catalog=catalog,
        holder=holder, recorder=recorder, drafts=drafts,
        engine=engine, user_a=holder["user"],
        reviewer=Session().query(User).filter(User.id == REVIEWER_A).one(),
        user_b=Session().query(User).filter(User.id == USER_B).one(),
    )


def _generate(harness, *, agent_id: str | None = None,
              prompt: str = "design a workflow with a manual start"):
    response = harness.client.post(
        "/api/v1/workflows/generate-from-agent",
        json={"prompt": prompt, **({"agent_id": agent_id} if agent_id else {})})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "designed"
    assert body["definition_digest"]
    return body


def _deploy(harness, workflow_id, digest, *, agent_id=None, approval_id=None):
    payload = {"definition_digest": digest}
    if agent_id:
        payload["agent_id"] = agent_id
    if approval_id:
        payload["approval_id"] = approval_id
    return harness.client.post(
        f"/api/v1/workflows/workflows/{workflow_id}/deploy", json=payload)


def _catalog_rows(harness):
    import json
    return json.loads(harness.catalog.read_text())


def _hitl_rows(harness):
    db = harness.Session()
    try:
        return db.query(HITLAction).all()
    finally:
        db.close()


def test_ready_positive_deploy_run_and_restart(harness):
    harness.drafts["draft"] = _draft_readonly()
    generated = _generate(harness, agent_id=AGENT_AUTO)
    workflow_id = generated["workflow_id"]
    digest = generated["definition_digest"]

    deployed = _deploy(harness, workflow_id, digest, agent_id=AGENT_AUTO)
    assert deployed.status_code == 200, deployed.text
    body = deployed.json()
    assert body["status"] == "deployed"
    assert body["scheduler_job_id"] is None
    assert body["manual_run_endpoint"].endswith(
        f"/workflows/{workflow_id}/execute")
    assert harness.recorder.calls == []

    rows = harness.client.get("/api/v1/workflows/workflows").json()
    assert [row["id"] for row in rows] == [workflow_id]
    deployment = rows[0]["deployment"]
    assert deployment["canonical_workflow_id"] == workflow_id
    assert deployment["definition_digest"] == digest
    assert deployment["tenant_id"] == TENANT_A
    assert deployment["workspace_id"] == WS_A
    assert deployment["triggers_activated"] is False

    # Duplicate deploy is idempotent: one row, no new effect.
    duplicate = _deploy(harness, workflow_id, digest, agent_id=AGENT_AUTO)
    assert duplicate.status_code == 200
    assert duplicate.json()["status"] == "already_deployed"
    assert [row["id"] for row in _catalog_rows(harness)] == [workflow_id]

    # Fresh-process simulation: drop the in-memory registration. The run path
    # must reload the scoped SQL blueprint, re-verify the digest, re-register
    # through the existing consumer and dispatch the real trigger handler.
    from advanced_workflow_orchestrator import get_orchestrator
    get_orchestrator().workflows.pop(workflow_id, None)
    run = harness.client.post(
        f"/api/v1/workflows/workflows/{workflow_id}/execute",
        json={"probe": True})
    assert run.status_code == 200, run.text
    run_body = run.json()
    assert run_body["status"] == "completed"
    assert any(item.get("step_id") == "start"
               and item.get("trigger") == "manual"
               for item in run_body["results"])
    lookup_result = next(
        item for item in run_body["results"] if item.get("step_id") == "lookup")
    assert lookup_result["status"] == "completed"
    assert "matches" in lookup_result
    assert harness.recorder.calls == []

    # A new session/engine reads the same durable row.
    fresh = sessionmaker(bind=harness.engine, expire_on_commit=False)()
    try:
        blueprint = fresh.query(Workflow).filter(
            Workflow.id == workflow_id).one()
        assert blueprint.status == "designed"
        assert blueprint.tenant_id == TENANT_A
    finally:
        fresh.close()
    assert _catalog_rows(harness)[0]["deployment"]["definition_digest"] == digest


def test_pending_approval_is_real_scoped_and_zero_catalog(harness):
    generated = _generate(harness, agent_id=AGENT_INTERN)
    workflow_id = generated["workflow_id"]
    digest = generated["definition_digest"]

    pending = _deploy(harness, workflow_id, digest, agent_id=AGENT_INTERN)
    assert pending.status_code == 200, pending.text
    body = pending.json()
    assert body["status"] == "pending_approval"
    assert body["approval_id"]
    assert body["scheduler_job_id"] is None
    assert _catalog_rows(harness) == []
    assert harness.recorder.calls == []

    rows = _hitl_rows(harness)
    assert len(rows) == 1
    row = rows[0]
    assert row.id == body["approval_id"]
    assert row.action_type == "deploy_workflow"
    assert row.status == "pending"
    assert row.tenant_id == TENANT_A
    assert row.workspace_id == WS_A
    assert row.user_id == USER_A
    assert row.params["workflow_id"] == workflow_id
    assert row.params["definition_digest"] == digest
    assert row.params["executor_agent_id"] == AGENT_INTERN

    repeated = _deploy(harness, workflow_id, digest, agent_id=AGENT_INTERN)
    assert repeated.status_code == 200
    assert repeated.json()["status"] == "pending_approval"
    assert repeated.json()["approval_id"] == body["approval_id"]
    assert len(_hitl_rows(harness)) == 1
    assert _catalog_rows(harness) == []


def test_approved_approval_consumes_exactly_once(harness):
    import asyncio
    from core.intervention_service import intervention_service

    generated = _generate(harness, agent_id=AGENT_INTERN)
    workflow_id = generated["workflow_id"]
    digest = generated["definition_digest"]
    pending = _deploy(harness, workflow_id, digest,
                      agent_id=AGENT_INTERN).json()

    approved = asyncio.run(intervention_service.approve_intervention(
        pending["approval_id"], REVIEWER_A))
    assert approved["success"] is True

    deployed = _deploy(harness, workflow_id, digest,
                       agent_id=AGENT_INTERN,
                       approval_id=pending["approval_id"])
    assert deployed.status_code == 200, deployed.text
    assert deployed.json()["status"] == "deployed"
    assert len(_catalog_rows(harness)) == 1
    row = _hitl_rows(harness)[0]
    assert row.params["deployment_consumed"]["workflow_id"] == workflow_id
    assert row.params["deployment_consumed"]["definition_digest"] == digest

    # Replaying the same approval/catalog state is idempotent.
    replay = _deploy(harness, workflow_id, digest,
                     agent_id=AGENT_INTERN,
                     approval_id=pending["approval_id"])
    assert replay.status_code == 200
    assert replay.json()["status"] == "already_deployed"
    assert len(_catalog_rows(harness)) == 1
    assert harness.recorder.calls == []


def test_rejected_foreign_and_unbound_approvals_have_zero_effect(harness):
    import asyncio
    from core.intervention_service import intervention_service

    generated = _generate(harness, agent_id=AGENT_INTERN)
    workflow_id = generated["workflow_id"]
    digest = generated["definition_digest"]
    pending = _deploy(harness, workflow_id, digest,
                      agent_id=AGENT_INTERN).json()
    rejected = asyncio.run(intervention_service.reject_intervention(
        pending["approval_id"], REVIEWER_A, "not approved"))
    assert rejected["success"] is True

    refused = _deploy(harness, workflow_id, digest,
                      agent_id=AGENT_INTERN,
                      approval_id=pending["approval_id"])
    assert refused.status_code == 409
    assert refused.json()["detail"]["error"] == "approval_not_approved"
    assert _catalog_rows(harness) == []

    foreign = _deploy(harness, workflow_id, digest,
                      agent_id=AGENT_INTERN,
                      approval_id="approval-does-not-exist")
    assert foreign.status_code == 404
    assert foreign.json()["detail"]["error"] == "approval_not_found"
    assert _catalog_rows(harness) == []
    assert harness.recorder.calls == []


def test_digest_agent_and_unbound_design_bindings(harness):
    generated = _generate(harness, agent_id=AGENT_AUTO)
    workflow_id = generated["workflow_id"]
    digest = generated["definition_digest"]

    wrong_digest = _deploy(
        harness, workflow_id, "0" * 64, agent_id=AGENT_AUTO)
    assert wrong_digest.status_code == 409
    assert wrong_digest.json()["detail"]["error"] == (
        "definition_digest_mismatch")
    assert _catalog_rows(harness) == []

    wrong_agent = _deploy(
        harness, workflow_id, digest, agent_id=AGENT_INTERN)
    assert wrong_agent.status_code == 409
    assert wrong_agent.json()["detail"]["error"] == "agent_binding_mismatch"
    assert _catalog_rows(harness) == []

    # Old unbound design: a UI-supplied high-maturity agent cannot grant
    # direct authority; it must go through a fresh explicit review.
    harness.drafts["draft"] = _draft_trigger()
    unbound = _generate(harness)
    assert "requested_executor_agent_id" not in unbound["provenance"]
    old_pending = _deploy(
        harness, unbound["workflow_id"], unbound["definition_digest"],
        agent_id=AGENT_AUTO)
    assert old_pending.status_code == 200
    assert old_pending.json()["status"] == "pending_approval"
    assert _catalog_rows(harness) == []


def test_scope_isolation_and_legacy_rows_preserved(harness):
    generated = _generate(harness, agent_id=AGENT_AUTO)
    workflow_id = generated["workflow_id"]
    digest = generated["definition_digest"]
    assert _deploy(harness, workflow_id, digest,
                   agent_id=AGENT_AUTO).json()["status"] == "deployed"

    harness.holder["user"] = harness.user_b
    assert harness.client.get(
        "/api/v1/workflows/workflows").json() == []
    assert harness.client.get(
        f"/api/v1/workflows/workflows/{workflow_id}").status_code == 404
    assert harness.client.post(
        f"/api/v1/workflows/workflows/{workflow_id}/execute",
        json={}).status_code == 404

    # Legacy rows without deployment metadata keep their previous behavior;
    # their isolation is not newly certified.
    legacy = {
        "id": "legacy-1", "name": "Legacy", "description": "",
        "version": "1", "nodes": [], "connections": [], "triggers": [],
        "enabled": True,
    }
    import json
    rows = _catalog_rows(harness)
    rows.append(legacy)
    harness.catalog.write_text(json.dumps(rows))
    visible_b = harness.client.get(
        "/api/v1/workflows/workflows").json()
    assert [row["id"] for row in visible_b] == ["legacy-1"]


def test_mandatory_hitl_checkpoint_survives_generated_run(harness, monkeypatch):
    from core.agent_governance_service import AgentGovernanceService

    monkeypatch.setattr(
        AgentGovernanceService, "enforce_action",
        lambda *args, **kwargs: {
            "proceed": True,
            "status": "PENDING_APPROVAL",
            "action_required": "WAIT_FOR_APPROVAL",
        })

    harness.drafts["draft"] = _draft_hitl()
    generated = _generate(harness, agent_id=AGENT_AUTO)
    workflow_id = generated["workflow_id"]
    digest = generated["definition_digest"]
    assert any(
        step["step_type"] == "approval_required"
        for step in generated["steps"])

    deployed = _deploy(harness, workflow_id, digest, agent_id=AGENT_AUTO)
    assert deployed.status_code == 200, deployed.text
    assert deployed.json()["status"] == "deployed"

    run = harness.client.post(
        f"/api/v1/workflows/workflows/{workflow_id}/execute",
        json={"amount": 5})
    assert run.status_code == 200, run.text
    assert run.json()["status"] == "waiting_approval"

    rows = _hitl_rows(harness)
    checkpoint = next(
        row for row in rows if row.action_type == "workflow_checkpoint")
    assert checkpoint.status == "pending"
    assert checkpoint.params["definition_id"] == workflow_id
    assert checkpoint.params["workspace_id"] == WS_A
    assert checkpoint.params["tenant_id"] == TENANT_A
    assert checkpoint.params["guarded_step"] == "record"
    assert checkpoint.params["guarded_digest"]
    # No guarded effect was dispatched while approval is pending.
    assert not any(
        item.get("step_id") == "record"
        for item in run.json()["results"])
    assert harness.recorder.calls == []


def test_literal_workflows_route_wins_over_generated_id_path(harness):
    # The advanced router exposes GET /{workflow_id}; the literal My Workflows
    # list must win by registration order, not be swallowed as a workflow id.
    listed = harness.client.get("/api/v1/workflows/workflows")
    assert listed.status_code == 200, listed.text
    assert isinstance(listed.json(), list)

    generated = _generate(harness, agent_id=AGENT_AUTO)
    blueprint = harness.client.get(
        f"/api/v1/workflows/{generated['workflow_id']}")
    assert blueprint.status_code == 200, blueprint.text
    assert blueprint.json()["workflow_id"] == generated["workflow_id"]


def test_existing_deployed_material_keeps_the_winner(harness):
    generated = _generate(harness, agent_id=AGENT_AUTO)
    workflow_id = generated["workflow_id"]
    digest = generated["definition_digest"]
    assert _deploy(harness, workflow_id, digest,
                   agent_id=AGENT_AUTO).json()["status"] == "deployed"

    import json
    rows = _catalog_rows(harness)
    rows[0]["deployment"]["definition_digest"] = "peer-material-digest"
    harness.catalog.write_text(json.dumps(rows))

    conflict = _deploy(harness, workflow_id, digest, agent_id=AGENT_AUTO)
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["error"] == "workflow_material_conflict"
    assert _catalog_rows(harness)[0]["deployment"][
        "definition_digest"] == "peer-material-digest"


def test_post_commit_uncertainty_is_reported_not_rolled_back(harness, monkeypatch):
    import core.workflow_endpoints as endpoints_module

    real_mutate = endpoints_module.mutate_workflows

    def write_then_fail(mutator):
        real_mutate(mutator)
        raise RuntimeError("simulated post-commit readback failure")

    monkeypatch.setattr(endpoints_module, "mutate_workflows", write_then_fail)
    generated = _generate(harness, agent_id=AGENT_AUTO)
    workflow_id = generated["workflow_id"]
    digest = generated["definition_digest"]

    response = _deploy(harness, workflow_id, digest, agent_id=AGENT_AUTO)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "committed_unverified"
    # The row really exists: the response must not claim rollback/no effect.
    assert _catalog_rows(harness)[0]["id"] == workflow_id


def test_recurring_deploy_never_schedules_and_explicit_schedule_is_separate(
        harness):
    harness.drafts["draft"] = _draft_recurring()
    generated = _generate(
        harness, agent_id=AGENT_AUTO, prompt="recurring daily workflow")
    workflow_id = generated["workflow_id"]
    digest = generated["definition_digest"]
    assert generated["execution_mode"] == "recurring_automation"

    deployed = _deploy(harness, workflow_id, digest, agent_id=AGENT_AUTO)
    assert deployed.status_code == 200, deployed.text
    body = deployed.json()
    assert body["status"] == "deployed"
    assert body["scheduler_job_id"] is None
    assert body["execution_mode"] == "recurring_automation"
    assert harness.recorder.calls == []
    row = _catalog_rows(harness)[0]
    assert row["deployment"]["triggers_activated"] is False

    scheduled = harness.client.post(
        f"/api/v1/workflows/workflows/{workflow_id}/schedule",
        json={"trigger_type": "cron",
              "trigger_config": {"hour": 9, "minute": 0}})
    assert scheduled.status_code == 200, scheduled.text
    assert scheduled.json()["success"] is True
    assert len(harness.recorder.calls) == 1
    args, kwargs = harness.recorder.calls[0]
    assert args[0] == workflow_id
    assert kwargs.get("authorized") is True


def test_corrupt_catalog_refuses_deploy_and_preserves_bytes(harness):
    generated = _generate(harness, agent_id=AGENT_AUTO)
    corrupt = b'{"legacy": '
    harness.catalog.write_bytes(corrupt)

    response = _deploy(harness, generated["workflow_id"],
                       generated["definition_digest"], agent_id=AGENT_AUTO)
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"] == "workflow_store_unreadable"
    assert detail["possible_effect"] is False
    assert harness.catalog.read_bytes() == corrupt
    assert _hitl_rows(harness) == []


def test_wrong_shape_catalog_refuses_mutation(harness):
    generated = _generate(harness, agent_id=AGENT_AUTO)
    wrong_shape = b'{"workflows": []}'
    harness.catalog.write_bytes(wrong_shape)

    response = _deploy(harness, generated["workflow_id"],
                       generated["definition_digest"], agent_id=AGENT_AUTO)
    assert response.status_code == 503, response.text
    assert response.json()["detail"]["error"] == "workflow_store_unreadable"
    assert harness.catalog.read_bytes() == wrong_shape


def test_corrupt_catalog_refuses_legacy_create_writer(harness):
    corrupt = b'not json at all'
    harness.catalog.write_bytes(corrupt)
    payload = {
        "name": "Legacy writer", "description": "", "version": "1.0",
        "nodes": [], "connections": [], "triggers": [], "enabled": True,
    }
    response = harness.client.post(
        "/api/v1/workflows/workflows", json=payload)
    assert response.status_code == 503, response.text
    assert response.json()["detail"]["error"] == "workflow_store_unreadable"
    assert harness.catalog.read_bytes() == corrupt


def test_lock_failure_refuses_write(harness, monkeypatch):
    import fcntl

    generated = _generate(harness, agent_id=AGENT_AUTO)
    before = harness.catalog.read_bytes()

    def failing_flock(*args, **kwargs):
        raise OSError("simulated lock failure")

    monkeypatch.setattr(fcntl, "flock", failing_flock)
    response = _deploy(harness, generated["workflow_id"],
                       generated["definition_digest"], agent_id=AGENT_AUTO)
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"] == "workflow_store_lock_unavailable"
    assert detail["possible_effect"] is False
    assert harness.catalog.read_bytes() == before


def test_post_commit_readback_failure_is_unknown_not_rollback(
        harness, monkeypatch):
    import core.workflow_endpoints as endpoints_module

    real_read = endpoints_module._read_catalog_row
    real_mutate = endpoints_module.mutate_workflows

    def write_then_fail(mutator):
        real_mutate(mutator)
        raise RuntimeError("simulated post-commit failure")

    monkeypatch.setattr(
        endpoints_module, "_read_catalog_row", lambda workflow_id: None)
    monkeypatch.setattr(endpoints_module, "mutate_workflows", write_then_fail)
    generated = _generate(harness, agent_id=AGENT_AUTO)
    response = _deploy(harness, generated["workflow_id"],
                       generated["definition_digest"], agent_id=AGENT_AUTO)
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"] == "deployment_write_unknown"
    assert detail["possible_effect"] is True
    assert detail["operation_id"]

    # The bytes really were committed even though readback was unavailable.
    monkeypatch.setattr(endpoints_module, "_read_catalog_row", real_read)
    assert _catalog_rows(harness)[0]["id"] == generated["workflow_id"]


def test_already_deployed_replay_verifies_exact_bindings(harness):
    import json

    generated = _generate(harness, agent_id=AGENT_AUTO)
    workflow_id = generated["workflow_id"]
    digest = generated["definition_digest"]
    assert _deploy(harness, workflow_id, digest,
                   agent_id=AGENT_AUTO).json()["status"] == "deployed"

    rows = _catalog_rows(harness)
    rows[0]["deployment"]["owner_user_id"] = "someone-else"
    harness.catalog.write_text(json.dumps(rows))
    tampered = _deploy(harness, workflow_id, digest, agent_id=AGENT_AUTO)
    assert tampered.status_code == 409, tampered.text
    detail = tampered.json()["detail"]
    assert detail["error"] == "deployment_binding_mismatch"
    assert "owner_user_id" in detail["reasons"]

    rows = _catalog_rows(harness)
    rows[0]["deployment"]["owner_user_id"] = USER_A
    rows[0]["deployment"]["executor_agent_id"] = AGENT_INTERN
    harness.catalog.write_text(json.dumps(rows))
    tampered_agent = _deploy(harness, workflow_id, digest,
                             agent_id=AGENT_AUTO)
    assert tampered_agent.status_code == 409
    assert "executor_agent_id" in tampered_agent.json()["detail"]["reasons"]


def test_already_deployed_replay_verifies_consumed_approval(harness):
    import asyncio
    import json
    from core.intervention_service import intervention_service

    generated = _generate(harness, agent_id=AGENT_INTERN)
    workflow_id = generated["workflow_id"]
    digest = generated["definition_digest"]
    pending = _deploy(harness, workflow_id, digest,
                      agent_id=AGENT_INTERN).json()
    approved = asyncio.run(intervention_service.approve_intervention(
        pending["approval_id"], REVIEWER_A))
    assert approved["success"] is True
    assert _deploy(harness, workflow_id, digest, agent_id=AGENT_INTERN,
                   approval_id=pending["approval_id"]).json()[
                       "status"] == "deployed"

    rows = _catalog_rows(harness)
    rows[0]["deployment"]["approval_id"] = "unbound-approval"
    harness.catalog.write_text(json.dumps(rows))
    replay = _deploy(harness, workflow_id, digest, agent_id=AGENT_INTERN,
                     approval_id=pending["approval_id"])
    assert replay.status_code == 409, replay.text
    assert replay.json()["detail"]["error"] == "deployment_binding_mismatch"


class _PausedEditor:
    def __init__(self, entered, release):
        self.entered = entered
        self.release = release

    async def parse_workflow_edit_command(self, command, workflow):
        self.entered.set()
        await self.release.wait()
        return SimpleNamespace(
            confidence=0.9, reasoning="scratch paused edit", operations=[])

    async def apply_edit_plan(self, plan, workflow):
        modified = dict(workflow)
        modified["name"] = str(workflow.get("name") or "") + " edited"
        return modified

    def _rule_based_parse(self, command, workflow):
        raise AssertionError("rule-based fallback not expected")


def _create_legacy(harness):
    payload = {
        "id": "legacy-edit-1", "name": "Legacy edit target",
        "description": "", "version": "1.0", "nodes": [],
        "connections": [], "triggers": [], "enabled": True,
    }
    response = harness.client.post(
        "/api/v1/workflows/workflows", json=payload)
    assert response.status_code == 200, response.text


def _run_interleaved_edit(harness, monkeypatch, *, mutate_target=False):
    import asyncio
    import httpx
    import core.workflow_endpoints as endpoints_module

    entered = asyncio.Event()
    release = asyncio.Event()
    editor = _PausedEditor(entered, release)

    async def fake_get_editor():
        return editor

    monkeypatch.setattr(endpoints_module, "AI_EDITOR_AVAILABLE", True)
    monkeypatch.setattr(endpoints_module, "get_workflow_editor", fake_get_editor)

    _create_legacy(harness)
    generated = _generate(harness, agent_id=AGENT_AUTO)

    async def scenario():
        transport = httpx.ASGITransport(app=harness.app)
        async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver") as client:
            edit_task = asyncio.create_task(client.post(
                "/api/v1/workflows/workflows/legacy-edit-1/edit",
                json={"command": "rename it"}))
            await entered.wait()

            # Actual deploy command commits an unrelated generated row while
            # the legacy edit is paused after its snapshot.
            deployed = await client.post(
                f"/api/v1/workflows/workflows/{generated['workflow_id']}/deploy",
                json={"definition_digest": generated["definition_digest"],
                      "agent_id": AGENT_AUTO})
            assert deployed.status_code == 200, deployed.text
            assert deployed.json()["status"] == "deployed"

            if mutate_target:
                def _touch(rows):
                    for row in rows:
                        if row.get("id") == "legacy-edit-1":
                            row["description"] = "concurrent winner"
                            return True, None
                    return False, None
                endpoints_module.mutate_workflows(_touch)

            release.set()
            edit_response = await edit_task
            return edit_response

    return asyncio.run(scenario()), generated


def test_paused_legacy_edit_preserves_concurrent_deploy(harness, monkeypatch):
    response, generated = _run_interleaved_edit(harness, monkeypatch)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    ids = {row["id"] for row in _catalog_rows(harness)}
    assert ids == {"legacy-edit-1", generated["workflow_id"]}
    legacy = next(row for row in _catalog_rows(harness)
                  if row["id"] == "legacy-edit-1")
    assert legacy["name"] == "Legacy edit target edited"
    deployed = next(row for row in _catalog_rows(harness)
                    if row["id"] == generated["workflow_id"])
    assert deployed["deployment"]["definition_digest"] == (
        generated["definition_digest"])


def test_paused_legacy_edit_refuses_stale_same_row(harness, monkeypatch):
    response, generated = _run_interleaved_edit(
        harness, monkeypatch, mutate_target=True)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is False
    assert "changed while it was being edited" in body["message"]
    rows = _catalog_rows(harness)
    legacy = next(row for row in rows if row["id"] == "legacy-edit-1")
    assert legacy["description"] == "concurrent winner"
    assert {row["id"] for row in rows} == {
        "legacy-edit-1", generated["workflow_id"]}


def test_actor_demoted_before_commit_refuses_without_write(harness, monkeypatch):
    import core.workflow_endpoints as endpoints_module

    real_mutate = endpoints_module.mutate_workflows

    def demote_then_mutate(mutator):
        db = harness.Session()
        try:
            actor = db.query(User).filter(User.id == USER_A).one()
            actor.role = "member"
            db.commit()
        finally:
            db.close()
        return real_mutate(mutator)

    monkeypatch.setattr(
        endpoints_module, "mutate_workflows", demote_then_mutate)
    generated = _generate(harness, agent_id=AGENT_AUTO)
    response = _deploy(harness, generated["workflow_id"],
                       generated["definition_digest"], agent_id=AGENT_AUTO)
    assert response.status_code == 403, response.text
    detail = response.json()["detail"]
    assert detail["error"] == "current_authority_changed"
    assert detail["possible_effect"] is False
    assert _catalog_rows(harness) == []


def test_executor_demoted_before_commit_refuses_without_write(harness, monkeypatch):
    import core.workflow_endpoints as endpoints_module

    real_mutate = endpoints_module.mutate_workflows

    def demote_agent_then_mutate(mutator):
        db = harness.Session()
        try:
            agent = db.query(AgentRegistry).filter(
                AgentRegistry.id == AGENT_AUTO).one()
            agent.confidence_score = 0.6
            db.commit()
        finally:
            db.close()
        return real_mutate(mutator)

    monkeypatch.setattr(
        endpoints_module, "mutate_workflows", demote_agent_then_mutate)
    generated = _generate(harness, agent_id=AGENT_AUTO)
    response = _deploy(harness, generated["workflow_id"],
                       generated["definition_digest"], agent_id=AGENT_AUTO)
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["error"] == "executor_authority_changed"
    assert detail["possible_effect"] is False
    assert _catalog_rows(harness) == []


def test_already_deployed_replay_refuses_revoked_executor(harness):
    generated = _generate(harness, agent_id=AGENT_AUTO)
    workflow_id = generated["workflow_id"]
    digest = generated["definition_digest"]
    assert _deploy(harness, workflow_id, digest,
                   agent_id=AGENT_AUTO).json()["status"] == "deployed"

    db = harness.Session()
    try:
        agent = db.query(AgentRegistry).filter(
            AgentRegistry.id == AGENT_AUTO).one()
        agent.confidence_score = 0.6
        db.commit()
    finally:
        db.close()

    replay = _deploy(harness, workflow_id, digest, agent_id=AGENT_AUTO)
    assert replay.status_code == 409, replay.text
    detail = replay.json()["detail"]
    assert detail["error"] == "deployment_binding_mismatch"
    assert "current_authority_changed" in detail["reasons"]


def test_authority_claim_holds_db_lock_across_catalog_write(harness, monkeypatch):
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import OperationalError
    import core.workflow_endpoints as endpoints_module

    generated = _generate(harness, agent_id=AGENT_AUTO)
    real_write = endpoints_module._atomic_write_workflows
    peer_result = {}

    def write_with_peer_revocation(rows):
        # The conditional claim transaction is held here, immediately before
        # the file replace. A peer revocation must not be able to commit
        # between the claim and the file write.
        peer_engine = create_engine(
            str(harness.engine.url),
            connect_args={"check_same_thread": False, "timeout": 0.05})
        try:
            with peer_engine.connect() as conn:
                conn.execute(text(
                    "UPDATE users SET is_active = 0, status = 'disabled' "
                    "WHERE id = :uid"), {"uid": USER_A})
                conn.commit()
            peer_result["committed"] = True
        except OperationalError:
            peer_result["committed"] = False
        finally:
            peer_engine.dispose()
        real_write(rows)

    monkeypatch.setattr(
        endpoints_module, "_atomic_write_workflows",
        write_with_peer_revocation)
    response = _deploy(harness, generated["workflow_id"],
                       generated["definition_digest"], agent_id=AGENT_AUTO)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "deployed"
    assert peer_result["committed"] is False
    assert _catalog_rows(harness)[0]["deployment"]["authority"][
        "actor_user_id"] == USER_A

    db = harness.Session()
    try:
        actor = db.query(User).filter(User.id == USER_A).one()
        assert actor.is_active is True
        assert actor.status == "active"
    finally:
        db.close()


def test_sql_claim_commit_failure_keeps_file_effect(harness, monkeypatch):
    import core.workflow_endpoints as endpoints_module

    generated = _generate(harness, agent_id=AGENT_AUTO)

    def fail_commit(db):
        raise RuntimeError("simulated SQL commit failure")

    monkeypatch.setattr(
        endpoints_module, "_commit_authority_claim", fail_commit)
    response = _deploy(harness, generated["workflow_id"],
                       generated["definition_digest"], agent_id=AGENT_AUTO)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "committed_unverified"
    assert body["possible_effect"] is True
    assert body["operation_id"]
    # The file effect is real and must not be reported as rollback.
    assert _catalog_rows(harness)[0]["id"] == generated["workflow_id"]
