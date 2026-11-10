"""Goal14 guided public agent-create boundary controls.

Real scratch SQLite + real FastAPI route + real JWT. The guided factory (the
only model-facing component) is replaced by a deterministic double; the route,
authority resolution, decision writer, audit receipt, replay and scheduler
boundary stay real.

The matrix covers: current active authority, forged body identity/scope/tier,
concurrent actor change, exact scope, durable receipt, replay, changed
material, NULL/{} exact identity, scheduler-once, foreign acting-agent
reference, and same-scope acting-agent approval.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from api.agent_onboarding_routes import router as onboarding_router
from api.approvals_routes import router as approvals_router
from core.auth import create_access_token
from core.database import Base, get_db
from core.models import (
    AgentRegistry,
    AuditLog,
    HITLAction,
    Tenant,
    User,
    Workspace,
)

BLUEPRINT = {
    "name": "Guided Assistant",
    "description": "Helps the operations team",
    "category": "Operations",
    "capabilities": ["read_orders", "draft_update"],
    "template": "ops_coordinator",
    "configuration": {
        "system_prompt": "Help with operations work",
        "constraints": ["require human approval for destructive actions"],
    },
}


class FakeGuidedFactory:
    """Deterministic replacement for the only model-facing component."""

    def __init__(self, blueprint=None, on_design=None):
        self.blueprint = dict(blueprint or BLUEPRINT)
        self.on_design = on_design

    async def design_agent(self, goal, context=None):
        if self.on_design is not None:
            self.on_design()
        return dict(self.blueprint)


@pytest.fixture
def world(tmp_path: Path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'guided.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    # The public approvals route's intervention/resume services use the
    # process SessionLocal. Point it at this scratch world so the real route
    # and the resume bridge see the same durable HITL row.
    import core.database as database
    monkeypatch.setattr(database, "SessionLocal", Session)
    with Session() as db:
        db.add_all([
            Tenant(id="company", name="Company", subdomain="company",
                   edition="personal", is_active=True),
            Tenant(id="other", name="Other", subdomain="other",
                   edition="personal", is_active=True),
        ])
        db.add_all([
            Workspace(id="ws-a", name="A", tenant_id="company"),
            Workspace(id="ws-b", name="B", tenant_id="other"),
        ])
        db.add_all([
            User(id="member", tenant_id="company", workspace_id="ws-a",
                 email="member@example.test", hashed_password="x",
                 first_name="M", last_name="V", role="member",
                 status="active", is_active=True),
            User(id="inactive", tenant_id="company", workspace_id="ws-a",
                 email="inactive@example.test", hashed_password="x",
                 first_name="I", last_name="V", role="member",
                 status="inactive", is_active=False),
            User(id="foreign", tenant_id="other", workspace_id="ws-b",
                 email="foreign@example.test", hashed_password="x",
                 first_name="F", last_name="V", role="member",
                 status="active", is_active=True),
            User(id="reviewer", tenant_id="company", workspace_id="ws-a",
                 email="reviewer@example.test", hashed_password="x",
                 first_name="R", last_name="V", role="team_lead",
                 status="active", is_active=True),
            User(id="foreign-reviewer", tenant_id="other", workspace_id="ws-b",
                 email="foreign-reviewer@example.test", hashed_password="x",
                 first_name="F", last_name="R", role="team_lead",
                 status="active", is_active=True),
        ])
        db.add_all([
            AgentRegistry(
                id="acting-agent", name="Acting Agent", category="Operations",
                module_path="tests.guided", class_name="ActingAgent",
                status="student", tenant_id="company", workspace_id="ws-a",
                confidence_score=0.2,
            ),
            AgentRegistry(
                id="foreign-agent", name="Foreign Agent", category="Operations",
                module_path="tests.guided", class_name="ForeignAgent",
                status="student", tenant_id="other", workspace_id="ws-b",
                confidence_score=0.2,
            ),
        ])
        db.commit()
    return {"engine": engine, "Session": Session, "db_url": engine.url}


def _client(world):
    app = FastAPI()
    app.include_router(onboarding_router)
    app.include_router(approvals_router)

    def override():
        db = world["Session"]()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    return TestClient(app)


def _token(world, user_id: str) -> str:
    with world["Session"]() as db:
        return create_access_token({"sub": user_id}, user=db.get(User, user_id))


def _post(client, token, body, operation_id="guided-op-1"):
    return client.post(
        f"/api/agents/guided?operation_id={operation_id}",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )


def _factory(monkeypatch, *, blueprint=None, on_design=None):
    factory = FakeGuidedFactory(blueprint=blueprint, on_design=on_design)
    monkeypatch.setattr(
        "api.agent_onboarding_routes.get_guided_agent_factory",
        lambda: factory,
    )
    return factory


def test_guided_create_binds_current_scope_receipt_and_replay(world, monkeypatch):
    _factory(monkeypatch)
    client = _client(world)
    token = _token(world, "member")
    body = {
        "goal": "Keep the operations queue tidy",
        "context": "Use the order tracker",
        # Forged body identity/scope/tier fields must not mint authority.
        "tenant_id": "other",
        "workspace_id": "ws-b",
        "user_id": "foreign",
        "status": "autonomous",
        "confidence_score": 0.99,
        "maturity": "autonomous",
    }
    response = _post(client, token, body)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    agent_id = data["agent_id"]
    assert data["operation_id"] == "agent:create:guided-op-1"
    assert data["audit_id"] == "agent:create:guided-op-1"
    assert data["verification"]["status"] == "verified"

    with world["Session"]() as db:
        agent = db.get(AgentRegistry, agent_id)
        assert agent is not None
        assert agent.name == BLUEPRINT["name"]
        assert agent.category == BLUEPRINT["category"]
        assert agent.tenant_id == "company"
        assert agent.workspace_id == "ws-a"
        assert agent.status == "student"
        assert float(agent.confidence_score) == pytest.approx(0.1)
        assert agent.user_id == "member"
        assert agent.parent_agent_id is None
        assert agent.capabilities == BLUEPRINT["capabilities"]
        assert agent.configuration["role"] == "ops_coordinator"
        assert agent.configuration["learning"]["teacher_agent_id"] == (
            "atom_main")
        audit = db.get(AuditLog, "agent:create:guided-op-1")
        assert audit is not None
        assert audit.action == "agent_created"
        assert audit.user_id == "member"
        assert audit.tenant_id == "company"

    replay = _post(client, token, body)
    assert replay.status_code == 201, replay.text
    assert replay.json()["data"]["agent_id"] == agent_id
    with world["Session"]() as db:
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.id == agent_id).scalar() == 1
        assert db.query(func.count(AuditLog.id)).filter(
            AuditLog.id == "agent:create:guided-op-1").scalar() == 1


def test_guided_create_concurrent_deactivation_is_refused(world, monkeypatch):
    def deactivate():
        with world["Session"]() as peer:
            user = peer.get(User, "member")
            user.is_active = False
            user.status = "inactive"
            peer.commit()

    _factory(monkeypatch, on_design=deactivate)
    client = _client(world)
    token = _token(world, "member")
    response = _post(client, token, {
        "goal": "Create while authority is changing",
    }, operation_id="guided-op-race")
    assert response.status_code == 403, response.text
    with world["Session"]() as db:
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.name == BLUEPRINT["name"]).scalar() == 0
        assert db.get(AuditLog, "agent:create:guided-op-race") is None


def test_guided_create_inactive_user_is_refused(world, monkeypatch):
    _factory(monkeypatch)
    client = _client(world)
    token = _token(world, "inactive")
    response = _post(client, token, {"goal": "Create without authority"})
    assert response.status_code in (401, 403), response.text
    with world["Session"]() as db:
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.name == BLUEPRINT["name"]).scalar() == 0


def test_guided_create_null_empty_schedule_material_conflicts(
        world, monkeypatch):
    _factory(monkeypatch)
    client = _client(world)
    token = _token(world, "member")
    body = {
        "goal": "Create with exact material",
        "schedule_config": None,
    }
    first = _post(client, token, body, operation_id="guided-null")
    assert first.status_code == 201, first.text
    agent_id = first.json()["data"]["agent_id"]

    changed = dict(body)
    changed["schedule_config"] = {}
    conflict = _post(client, token, changed, operation_id="guided-null")
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["error"]["code"] == (
        "OPERATION_CONFLICT")

    unchanged = _post(client, token, body, operation_id="guided-null")
    assert unchanged.status_code == 201, unchanged.text
    assert unchanged.json()["data"]["verification"]["status"] == (
        "already_applied")
    with world["Session"]() as db:
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.id == agent_id).scalar() == 1
        assert db.get(AgentRegistry, agent_id).schedule_config is None


def test_guided_create_scheduler_runs_only_on_first_verified_create(
        world, monkeypatch):
    _factory(monkeypatch)
    client = _client(world)
    token = _token(world, "member")
    calls = []

    class FakeScheduler:
        def schedule_agent(self, agent_id, schedule_config):
            calls.append((agent_id, dict(schedule_config)))

    from core.scheduler import AgentScheduler

    monkeypatch.setattr(AgentScheduler, "get_instance", lambda: FakeScheduler())
    body = {
        "goal": "Create a scheduled guided agent",
        "schedule_config": {"active": True, "cron": "0 * * * *"},
    }
    first = _post(client, token, body, operation_id="guided-scheduled")
    assert first.status_code == 201, first.text
    replay = _post(client, token, body, operation_id="guided-scheduled")
    assert replay.status_code == 201, replay.text
    assert len(calls) == 1

    changed = dict(body)
    changed["schedule_config"] = {"active": True, "cron": "1 * * * *"}
    conflict = _post(client, token, changed, operation_id="guided-scheduled")
    assert conflict.status_code == 409, conflict.text
    assert len(calls) == 1


def test_guided_create_foreign_acting_agent_is_refused(
        world, monkeypatch):
    _factory(monkeypatch)
    client = _client(world)
    token = _token(world, "member")
    response = _post(client, token, {
        "goal": "Ask a foreign agent to create a helper",
        "acting_agent_id": "foreign-agent",
    }, operation_id="guided-foreign-acting")
    assert response.status_code == 404, response.text
    with world["Session"]() as db:
        assert db.query(func.count(HITLAction.id)).filter(
            HITLAction.agent_id == "foreign-agent").scalar() == 0
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.name == BLUEPRINT["name"]).scalar() == 0


def test_guided_create_same_scope_acting_agent_queues_scoped_review(
        world, monkeypatch):
    _factory(monkeypatch)
    client = _client(world)
    token = _token(world, "member")
    response = _post(client, token, {
        "goal": "Ask the local student to create a helper",
        "acting_agent_id": "acting-agent",
        "schedule_config": {"active": True, "cron": "0 * * * *"},
    }, operation_id="guided-acting-review")
    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["status"] == "pending_approval"
    assert data["hitl_action_id"]
    with world["Session"]() as db:
        row = db.get(HITLAction, data["hitl_action_id"])
        assert row is not None
        assert row.agent_id == "acting-agent"
        assert row.tenant_id == "company"
        assert row.workspace_id == "ws-a"
        assert row.status == "pending"
        assert "goal" in row.params
        assert "context" in row.params
        assert row.params["created_by_user"] == "member"
        assert row.params["tenant_id"] == "company"
        assert row.params["workspace_id"] == "ws-a"
        assert row.params["acting_agent_id"] == "acting-agent"
        assert row.params["schedule_config"] == {
            "active": True, "cron": "0 * * * *"}


def test_guided_create_is_create_only_and_preserves_existing_agent(
        world, monkeypatch):
    _factory(monkeypatch)
    with world["Session"]() as db:
        existing = AgentRegistry(
            id="existing-agent", name=BLUEPRINT["name"],
            category=BLUEPRINT["category"],
            module_path="core.generic_agent", class_name="GenericAgent",
            status="intern", confidence_score=0.7,
            tenant_id="company", workspace_id="ws-a",
            configuration={"keep": "original"},
        )
        db.add(existing)
        db.commit()

    client = _client(world)
    token = _token(world, "member")
    response = _post(client, token, {
        "goal": "Create another agent with the same displayed name",
    }, operation_id="guided-create-only")
    assert response.status_code == 201, response.text
    agent_id = response.json()["data"]["agent_id"]
    assert agent_id != "existing-agent"

    with world["Session"]() as db:
        original = db.get(AgentRegistry, "existing-agent")
        assert original.status == "intern"
        assert float(original.confidence_score) == pytest.approx(0.7)
        assert original.configuration == {"keep": "original"}
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.name == BLUEPRINT["name"]).scalar() == 2


def test_guided_create_generated_blueprint_cannot_mint_authority(
        world, monkeypatch):
    forged = dict(BLUEPRINT)
    forged.update({
        "status": "autonomous",
        "confidence_score": 0.99,
        "maturity": "autonomous",
        "tenant_id": "other",
        "workspace_id": "ws-b",
        "user_id": "foreign",
    })
    _factory(monkeypatch, blueprint=forged)
    client = _client(world)
    token = _token(world, "member")
    response = _post(client, token, {
        "goal": "Generate an agent with forged authority fields",
    }, operation_id="guided-forged-blueprint")
    assert response.status_code == 201, response.text
    with world["Session"]() as db:
        agent = db.get(AgentRegistry, response.json()["data"]["agent_id"])
        assert agent.status == "student"
        assert float(agent.confidence_score) == pytest.approx(0.1)
        assert agent.tenant_id == "company"
        assert agent.workspace_id == "ws-a"
        assert agent.user_id == "member"


def test_guided_create_replay_with_changed_generated_material_conflicts(
        world, monkeypatch):
    factory = FakeGuidedFactory()
    monkeypatch.setattr(
        "api.agent_onboarding_routes.get_guided_agent_factory",
        lambda: factory,
    )
    client = _client(world)
    token = _token(world, "member")
    body = {"goal": "Create with generated material"}
    first = _post(client, token, body, operation_id="guided-changed")
    assert first.status_code == 201, first.text
    agent_id = first.json()["data"]["agent_id"]

    changed_blueprint = dict(BLUEPRINT)
    changed_blueprint["name"] = "Different Guided Assistant"
    factory.blueprint = changed_blueprint
    conflict = _post(client, token, body, operation_id="guided-changed")
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["error"]["code"] == (
        "OPERATION_CONFLICT")
    with world["Session"]() as db:
        assert db.get(AgentRegistry, agent_id).name == BLUEPRINT["name"]
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.name == "Different Guided Assistant").scalar() == 0


def test_guided_create_readback_uncertainty_returns_503(
        world, monkeypatch):
    import core.agent_decision_write_service as writes

    _factory(monkeypatch)
    monkeypatch.setattr(writes, "_load_agent", lambda db, agent_id: None)
    client = _client(world)
    token = _token(world, "member")
    response = _post(client, token, {
        "goal": "Create with an unreadable target after commit",
    }, operation_id="guided-readback")
    assert response.status_code == 503, response.text
    assert response.json()["detail"]["error"]["code"] == (
        "AGENT_COMMITTED_UNVERIFIED")
    with world["Session"]() as db:
        agent = db.query(AgentRegistry).filter(
            AgentRegistry.name == BLUEPRINT["name"]).first()
        assert agent is not None
        assert db.get(AuditLog, "agent:create:guided-readback") is not None


def test_guided_create_commit_failure_reports_effect_unknown(
        world, monkeypatch):
    from sqlalchemy.orm import Session as SASession

    _factory(monkeypatch)
    original_commit = SASession.commit
    calls = {"n": 0}

    def flaky_commit(self):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("commit outcome unknown")
        return original_commit(self)

    monkeypatch.setattr(SASession, "commit", flaky_commit)
    client = _client(world)
    token = _token(world, "member")
    response = _post(client, token, {
        "goal": "Create while the commit outcome is unknown",
    }, operation_id="guided-rollback")
    assert response.status_code == 503, response.text
    assert response.json()["detail"]["error"]["code"] == "AGENT_EFFECT_UNKNOWN"
    with world["Session"]() as db:
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.name == BLUEPRINT["name"]).scalar() == 0
        assert db.get(AuditLog, "agent:create:guided-rollback") is None


def test_guided_create_acting_agent_deleted_during_generation_is_refused(
        world, monkeypatch):
    with world["Session"]() as db:
        agent = db.get(AgentRegistry, "acting-agent")
        agent.status = "autonomous"
        db.commit()

    def delete_acting():
        with world["Session"]() as peer:
            peer.query(AgentRegistry).filter(
                AgentRegistry.id == "acting-agent").delete()
            peer.commit()

    _factory(monkeypatch, on_design=delete_acting)
    client = _client(world)
    token = _token(world, "member")
    response = _post(client, token, {
        "goal": "Create after the acting agent disappears",
        "acting_agent_id": "acting-agent",
    }, operation_id="guided-acting-deleted")
    assert response.status_code == 404, response.text
    with world["Session"]() as db:
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.name == BLUEPRINT["name"]).scalar() == 0
        assert db.get(AuditLog, "agent:create:guided-acting-deleted") is None


def _set_autonomous_acting(world, confidence=0.99):
    with world["Session"]() as db:
        agent = db.get(AgentRegistry, "acting-agent")
        agent.status = "autonomous"
        agent.confidence_score = confidence
        db.commit()


def _race_acting_agent(world, monkeypatch, change):
    """Change the acting agent after the route snapshot, before the create."""
    _set_autonomous_acting(world)
    _factory(monkeypatch)
    from api import agent_onboarding_routes as route

    original = route._create_agent_decision

    def raced(db, **kwargs):
        with world["Session"]() as peer:
            agent = peer.get(AgentRegistry, "acting-agent")
            if change == "scope":
                agent.tenant_id = "other"
                agent.workspace_id = "ws-b"
            elif change == "status":
                agent.status = "student"
            elif change == "material":
                agent.confidence_score = 0.98
                agent.configuration = {"changed": True}
            elif change == "delete":
                peer.delete(agent)
            else:  # pragma: no cover
                raise AssertionError(change)
            peer.commit()
        return original(db, **kwargs)

    monkeypatch.setattr(route, "_create_agent_decision", raced)


@pytest.mark.parametrize("change", ["scope", "status", "material", "delete"])
def test_guided_create_parent_change_before_create_refuses(
        world, monkeypatch, change):
    _race_acting_agent(world, monkeypatch, change)
    scheduled = []

    class FakeScheduler:
        def schedule_agent(self, agent_id, schedule_config):
            scheduled.append(agent_id)

    from core.scheduler import AgentScheduler

    monkeypatch.setattr(AgentScheduler, "get_instance", lambda: FakeScheduler())
    client = _client(world)
    token = _token(world, "member")
    response = _post(client, token, {
        "goal": "Create with current acting authority",
        "acting_agent_id": "acting-agent",
        "schedule_config": {"active": True, "cron": "0 * * * *"},
    }, operation_id=f"guided-parent-{change}")
    assert response.status_code in (202, 403, 404, 409), response.text
    assert response.status_code != 201
    with world["Session"]() as db:
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.name == BLUEPRINT["name"]).scalar() == 0
        assert db.get(AuditLog, f"agent:create:guided-parent-{change}") is None
    assert scheduled == []


def test_guided_create_valid_autonomous_acting_agent(world, monkeypatch):
    _set_autonomous_acting(world)
    _factory(monkeypatch)
    scheduled = []

    class FakeScheduler:
        def schedule_agent(self, agent_id, schedule_config):
            scheduled.append(agent_id)

    from core.scheduler import AgentScheduler

    monkeypatch.setattr(AgentScheduler, "get_instance", lambda: FakeScheduler())
    client = _client(world)
    token = _token(world, "member")
    response = _post(client, token, {
        "goal": "Create with an allowed autonomous acting agent",
        "acting_agent_id": "acting-agent",
        "schedule_config": {"active": True, "cron": "0 * * * *"},
    }, operation_id="guided-valid-acting")
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["verification"]["status"] == "verified"
    with world["Session"]() as db:
        agent = db.get(AgentRegistry, data["agent_id"])
        assert agent.parent_agent_id == "acting-agent"
        audit = db.get(AuditLog, "agent:create:guided-valid-acting")
        assert audit is not None
        metadata = json.loads(audit.metadata_json)
        assert metadata["extra"]["parent_authority"]["id"] == (
            "acting-agent")
        assert metadata["extra"]["parent_authority"]["status"] == (
            "autonomous")
    assert scheduled == [data["agent_id"]]


def test_guided_create_replay_after_parent_material_change_conflicts(
        world, monkeypatch):
    _set_autonomous_acting(world)
    _factory(monkeypatch)
    client = _client(world)
    token = _token(world, "member")
    body = {
        "goal": "Create with an exact parent receipt",
        "acting_agent_id": "acting-agent",
    }
    first = _post(client, token, body, operation_id="guided-parent-replay")
    assert first.status_code == 201, first.text
    agent_id = first.json()["data"]["agent_id"]

    with world["Session"]() as db:
        parent = db.get(AgentRegistry, "acting-agent")
        parent.confidence_score = 0.98
        db.commit()

    replay = _post(client, token, body, operation_id="guided-parent-replay")
    assert replay.status_code == 409, replay.text
    assert replay.json()["detail"]["error"]["code"] == "AUTHORITY_CHANGED"
    with world["Session"]() as db:
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.id == agent_id).scalar() == 1
        assert db.query(func.count(AuditLog.id)).filter(
            AuditLog.id == "agent:create:guided-parent-replay").scalar() == 1


def _queue_guided_hitl(
    world, monkeypatch, operation_id="guided-hitl-queue",
    schedule_config=None,
):
    with world["Session"]() as db:
        agent = db.get(AgentRegistry, "acting-agent")
        agent.status = "student"
        db.commit()
    _factory(monkeypatch)
    client = _client(world)
    token = _token(world, "member")
    body = {
        "goal": "Queue a reviewed guided helper",
        "acting_agent_id": "acting-agent",
    }
    if schedule_config is not None:
        body["schedule_config"] = schedule_config
    response = _post(client, token, body, operation_id=operation_id)
    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["status"] == "pending_approval"
    return data["hitl_action_id"]


def _decide_approval(
    client, token, action_id, decision="approved", modified_params=None,
):
    payload = {"decision": decision}
    if modified_params is not None:
        payload["modified_params"] = modified_params
    return client.post(
        f"/api/agents/approvals/{action_id}",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )


def test_guided_hitl_approval_creates_one_reviewed_agent(world, monkeypatch):
    scheduled = []

    class FakeScheduler:
        def schedule_agent(self, agent_id, schedule_config):
            scheduled.append((agent_id, dict(schedule_config)))

    from core.scheduler import AgentScheduler

    monkeypatch.setattr(AgentScheduler, "get_instance", lambda: FakeScheduler())
    action_id = _queue_guided_hitl(
        world, monkeypatch,
        schedule_config={"active": True, "cron": "0 * * * *"},
    )
    client = _client(world)
    reviewer_token = _token(world, "reviewer")
    response = _decide_approval(client, reviewer_token, action_id)
    assert response.status_code == 200, response.text
    body = response.json()
    resume = body["resume"]
    assert resume["resumed"] is True, body
    assert resume["kind"] == "guided_create"
    agent_id = resume["agent_id"]

    with world["Session"]() as db:
        agent = db.get(AgentRegistry, agent_id)
        assert agent.name == BLUEPRINT["name"]
        assert agent.category == BLUEPRINT["category"]
        assert agent.capabilities == BLUEPRINT["capabilities"]
        assert agent.configuration["role"] == "ops_coordinator"
        assert agent.configuration["learning"]["teacher_agent_id"] == (
            "atom_main")
        assert agent.status == "student"
        assert float(agent.confidence_score) == pytest.approx(0.1)
        assert agent.user_id == "member"
        assert agent.parent_agent_id == "acting-agent"
        assert agent.tenant_id == "company"
        assert agent.workspace_id == "ws-a"
        audit = db.get(
            AuditLog, f"agent:create:guided-hitl:{action_id}")
        assert audit is not None
        assert audit.action == "agent_created"
        assert audit.user_id == "reviewer"
        assert audit.tenant_id == "company"
        row = db.get(HITLAction, action_id)
        assert row.status == "approved"
        assert row.reviewed_by == "reviewer"
    assert scheduled == [(agent_id, {"active": True, "cron": "0 * * * *"})]

    # Direct duplicate resume is idempotent: one child, one receipt, one
    # schedule even if the durable continuation is replayed.
    from core.hitl_resume import resume_after_hitl_decision

    replay = asyncio.run(resume_after_hitl_decision(
        action_id, approved=True, reviewer_id="reviewer"))
    assert replay["resumed"] is True, replay
    assert replay["agent_id"] == agent_id
    with world["Session"]() as db:
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.id == agent_id).scalar() == 1
        assert db.query(func.count(AuditLog.id)).filter(
            AuditLog.id == f"agent:create:guided-hitl:{action_id}").scalar() == 1
    assert len(scheduled) == 1

    duplicate = _decide_approval(client, reviewer_token, action_id)
    assert duplicate.status_code == 400, duplicate.text
    with world["Session"]() as db:
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.id == agent_id).scalar() == 1
        assert db.query(func.count(AuditLog.id)).filter(
            AuditLog.id == f"agent:create:guided-hitl:{action_id}").scalar() == 1
    assert len(scheduled) == 1


def test_guided_hitl_rejection_creates_nothing(world, monkeypatch):
    action_id = _queue_guided_hitl(world, monkeypatch)
    client = _client(world)
    reviewer_token = _token(world, "reviewer")
    response = _decide_approval(
        client, reviewer_token, action_id, decision="rejected")
    assert response.status_code == 200, response.text
    resume = response.json()["resume"]
    assert resume["resumed"] is False
    assert resume["kind"] == "guided_create"
    assert resume["status"] == "rejected"
    with world["Session"]() as db:
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.name == BLUEPRINT["name"]).scalar() == 0
        assert db.query(func.count(AuditLog.id)).filter(
            AuditLog.id == f"agent:create:guided-hitl:{action_id}").scalar() == 0
        assert db.get(HITLAction, action_id).status == "rejected"


def test_guided_hitl_expired_does_not_create(world, monkeypatch):
    action_id = _queue_guided_hitl(world, monkeypatch)
    with world["Session"]() as db:
        row = db.get(HITLAction, action_id)
        row.status = "expired"
        db.commit()
    from core.hitl_resume import resume_after_hitl_decision

    result = asyncio.run(resume_after_hitl_decision(
        action_id, approved=True, reviewer_id="reviewer"))
    assert result["resumed"] is False
    assert result["reason"] == "action_not_approved"
    with world["Session"]() as db:
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.name == BLUEPRINT["name"]).scalar() == 0
        assert db.query(func.count(AuditLog.id)).filter(
            AuditLog.id == f"agent:create:guided-hitl:{action_id}").scalar() == 0


def test_guided_hitl_wrong_scope_reviewer_is_refused(world, monkeypatch):
    action_id = _queue_guided_hitl(world, monkeypatch)
    client = _client(world)
    foreign_token = _token(world, "foreign-reviewer")
    response = _decide_approval(client, foreign_token, action_id)
    assert response.status_code == 404, response.text
    with world["Session"]() as db:
        assert db.get(HITLAction, action_id).status == "pending"
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.name == BLUEPRINT["name"]).scalar() == 0
        assert db.query(func.count(AuditLog.id)).filter(
            AuditLog.id == f"agent:create:guided-hitl:{action_id}").scalar() == 0


def test_guided_hitl_modified_material_is_refused(world, monkeypatch):
    action_id = _queue_guided_hitl(world, monkeypatch)
    client = _client(world)
    reviewer_token = _token(world, "reviewer")
    response = _decide_approval(
        client, reviewer_token, action_id,
        modified_params={"name": "Tampered Name"})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["reason"] == "review_material_immutable"
    with world["Session"]() as db:
        assert db.get(HITLAction, action_id).status == "pending"
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.name == "Tampered Name").scalar() == 0
        assert db.query(func.count(AuditLog.id)).filter(
            AuditLog.id == f"agent:create:guided-hitl:{action_id}").scalar() == 0


def test_guided_hitl_stored_material_mismatch_is_refused(
        world, monkeypatch):
    action_id = _queue_guided_hitl(world, monkeypatch)
    with world["Session"]() as db:
        row = db.get(HITLAction, action_id)
        params = dict(row.params or {})
        params["name"] = "Tampered Stored Name"
        row.params = params
        db.commit()
    client = _client(world)
    reviewer_token = _token(world, "reviewer")
    response = _decide_approval(client, reviewer_token, action_id)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["reason"] == "review_material_mismatch"
    with world["Session"]() as db:
        assert db.get(HITLAction, action_id).status == "pending"
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.name == "Tampered Stored Name").scalar() == 0
        assert db.query(func.count(AuditLog.id)).filter(
            AuditLog.id == f"agent:create:guided-hitl:{action_id}").scalar() == 0


def test_guided_hitl_approval_survives_fresh_session(world, monkeypatch):
    action_id = _queue_guided_hitl(world, monkeypatch)
    world["engine"].dispose()
    fresh_engine = create_engine(
        str(world["db_url"]),
        connect_args={"check_same_thread": False},
    )
    FreshSession = sessionmaker(bind=fresh_engine, expire_on_commit=False)
    world["engine"] = fresh_engine
    world["Session"] = FreshSession
    import core.database as database

    monkeypatch.setattr(database, "SessionLocal", FreshSession)
    client = _client(world)
    reviewer_token = _token(world, "reviewer")
    response = _decide_approval(client, reviewer_token, action_id)
    assert response.status_code == 200, response.text
    resume = response.json()["resume"]
    assert resume["resumed"] is True, resume
    with world["Session"]() as db:
        agent = db.get(AgentRegistry, resume["agent_id"])
        assert agent is not None
        assert agent.parent_agent_id == "acting-agent"
        assert db.get(
            AuditLog, f"agent:create:guided-hitl:{action_id}") is not None
