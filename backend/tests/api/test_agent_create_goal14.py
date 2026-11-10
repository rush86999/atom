"""Goal14 public agent-create boundary controls.

Real scratch SQLite + real FastAPI route + real JWT. The test owns the rows and
never touches the live DB. It proves the public custom-create alias binds the
current actor/scope, forces STUDENT regardless of forged body identity/tier,
writes one durable operation receipt, replays without duplication, and refuses
a concurrent actor demotion at the claim boundary.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from api.agent_routes import router as agent_router
from core.auth import create_access_token
from core.database import Base, get_db
from core.models import AgentRegistry, AuditLog, Tenant, User, Workspace


@pytest.fixture
def world(tmp_path: Path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'create.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
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
            User(id="admin", tenant_id="company", workspace_id="ws-a",
                 email="admin@example.test", hashed_password="x",
                 first_name="A", last_name="D", role="workspace_admin",
                 status="active", is_active=True),
            User(id="member", tenant_id="company", workspace_id="ws-a",
                 email="member@example.test", hashed_password="x",
                 first_name="M", last_name="V", role="member",
                 status="active", is_active=True),
        ])
        db.commit()
    return {"engine": engine, "Session": Session}


def _client(world):
    app = FastAPI()
    app.include_router(agent_router)

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


def _post(client, token, body, operation_id="create-op-1"):
    return client.post(
        f"/api/agents/custom?operation_id={operation_id}",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )


def test_custom_create_forged_body_is_ignored_and_receipt_replays(world):
    client = _client(world)
    token = _token(world, "admin")
    body = {
        "name": "Scoped Create",
        "description": "created by the current admin",
        "category": "operations",
        "configuration": {"learning": {"role": "operations"}},
        "schedule_config": None,
        # Forged body identity/scope/tier must be ignored.
        "tenant_id": "other",
        "workspace_id": "ws-b",
        "user_id": "foreign",
        "status": "autonomous",
        "maturity": "autonomous",
        "confidence_score": 0.99,
    }
    response = _post(client, token, body)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    agent_id = data["agent_id"]
    assert data["operation_id"] == "agent:create:create-op-1"
    assert data["audit_id"] == "agent:create:create-op-1"
    assert data["verification"]["status"] == "verified"

    with world["Session"]() as db:
        agent = db.get(AgentRegistry, agent_id)
        assert agent is not None
        assert agent.name == "Scoped Create"
        assert agent.category == "operations"
        assert agent.tenant_id == "company"
        assert agent.workspace_id == "ws-a"
        assert agent.status == "student"
        assert float(agent.confidence_score) < 0.5
        assert agent.user_id is None
        audit = db.get(AuditLog, "agent:create:create-op-1")
        assert audit is not None
        assert audit.action == "agent_created"
        assert audit.event_type == "create"
        assert audit.user_id == "admin"
        assert audit.tenant_id == "company"
        assert audit.success is True

    replay = _post(client, token, body)
    assert replay.status_code == 201, replay.text
    assert replay.json()["data"]["agent_id"] == agent_id
    with world["Session"]() as db:
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.id == agent_id).scalar() == 1
        assert db.query(func.count(AuditLog.id)).filter(
            AuditLog.id == "agent:create:create-op-1").scalar() == 1


def test_custom_create_refuses_concurrent_actor_demotion(world, monkeypatch):
    from core import agent_decision_write_service as writes

    original_claim = writes._claim_actor

    def claim_after_demotion(db, actor):
        with world["Session"]() as peer:
            user = peer.get(User, "admin")
            user.role = "member"
            peer.commit()
        return original_claim(db, actor)

    monkeypatch.setattr(writes, "_claim_actor", claim_after_demotion)
    client = _client(world)
    token = _token(world, "admin")
    response = _post(client, token, {
        "name": "Racing Create",
        "category": "operations",
        "configuration": {},
    }, operation_id="create-op-race")
    assert response.status_code == 409, response.text
    with world["Session"]() as db:
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.name == "Racing Create").scalar() == 0
        assert db.get(AuditLog, "agent:create:create-op-race") is None


def test_custom_create_member_is_forbidden(world):
    client = _client(world)
    token = _token(world, "member")
    response = _post(client, token, {
        "name": "Member Create",
        "category": "operations",
        "configuration": {},
    }, operation_id="create-op-member")
    assert response.status_code == 403, response.text
    with world["Session"]() as db:
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.name == "Member Create").scalar() == 0


def test_custom_create_replay_with_changed_material_conflicts(world):
    client = _client(world)
    token = _token(world, "admin")
    body = {
        "name": "Bound Create",
        "category": "operations",
        "configuration": {},
    }
    first = _post(client, token, body, operation_id="create-op-bound")
    assert first.status_code == 201, first.text
    agent_id = first.json()["data"]["agent_id"]

    changed = dict(body)
    changed["name"] = "Different Name"
    replay = _post(client, token, changed, operation_id="create-op-bound")
    assert replay.status_code == 409, replay.text
    assert replay.json()["detail"]["error"]["code"] == "OPERATION_CONFLICT"
    with world["Session"]() as db:
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.name == "Different Name").scalar() == 0
        assert db.query(func.count(AuditLog.id)).filter(
            AuditLog.id == "agent:create:create-op-bound").scalar() == 1
        assert db.get(AgentRegistry, agent_id).name == "Bound Create"


@pytest.mark.parametrize("field", ["configuration", "schedule_config"])
@pytest.mark.parametrize(
    ("first", "changed", "label"),
    [(None, {}, "null-to-empty"), ({}, None, "empty-to-null")],
)
def test_custom_create_null_empty_request_change_conflicts(
        world, field, first, changed, label):
    """A changed request must conflict even when it normalizes to one row.

    NULL and {} are different reviewed material. The request digest binds
    the exact submitted value, so changing only this field cannot replay the
    original receipt.
    """
    client = _client(world)
    token = _token(world, "admin")
    operation_id = f"null-empty-request-{field}-{label}"
    body = {
        "name": "Exact Request",
        "category": "operations",
        "configuration": None,
        "schedule_config": None,
    }
    body[field] = first
    first_response = _post(client, token, body, operation_id=operation_id)
    assert first_response.status_code == 201, first_response.text

    body[field] = changed
    replay = _post(client, token, body, operation_id=operation_id)
    assert replay.status_code == 409, replay.text
    assert replay.json()["detail"]["error"]["code"] == "OPERATION_CONFLICT"


@pytest.mark.parametrize("field", ["configuration", "schedule_config"])
@pytest.mark.parametrize(
    ("first", "changed", "label"),
    [(None, {}, "null-to-empty"), ({}, None, "empty-to-null")],
)
def test_custom_create_stored_null_empty_mutation_refutes(
        world, field, first, changed, label):
    """A post-commit material change refutes the original receipt.

    The create stores NULL for an omitted field and {} for an explicit empty
    object. Mutating the stored value in the other direction is a real
    state change, so replay must return committed_unverified instead of
    claiming the original operation is already applied.
    """
    client = _client(world)
    token = _token(world, "admin")
    operation_id = f"null-empty-stored-{field}-{label}"
    body = {
        "name": "Stored Exact",
        "category": "operations",
        "configuration": None,
        "schedule_config": None,
    }
    body[field] = first
    first_response = _post(client, token, body, operation_id=operation_id)
    assert first_response.status_code == 201, first_response.text
    agent_id = first_response.json()["data"]["agent_id"]

    with world["Session"]() as db:
        agent = db.get(AgentRegistry, agent_id)
        setattr(agent, field, changed)
        db.commit()

    replay = _post(client, token, body, operation_id=operation_id)
    assert replay.status_code == 503, replay.text
    assert replay.json()["detail"]["error"]["code"] == (
        "AGENT_COMMITTED_UNVERIFIED")


@pytest.mark.parametrize("value", [None, {}])
def test_custom_create_unchanged_null_empty_replays_once(world, value):
    """The exact same NULL or {} request replays without a second effect."""
    client = _client(world)
    token = _token(world, "admin")
    operation_id = "unchanged-" + ("null" if value is None else "empty")
    body = {
        "name": "Unchanged Exact",
        "category": "operations",
        "configuration": value,
        "schedule_config": value,
    }
    first_response = _post(client, token, body, operation_id=operation_id)
    assert first_response.status_code == 201, first_response.text
    agent_id = first_response.json()["data"]["agent_id"]

    replay = _post(client, token, body, operation_id=operation_id)
    assert replay.status_code == 201, replay.text
    assert replay.json()["data"]["verification"]["status"] == "already_applied"
    with world["Session"]() as db:
        agent = db.get(AgentRegistry, agent_id)
        if value is None:
            assert agent.configuration is None
            assert agent.schedule_config is None
        else:
            assert agent.configuration == {}
            assert agent.schedule_config == {}
        assert db.query(func.count(AuditLog.id)).filter(
            AuditLog.id == f"agent:create:{operation_id}").scalar() == 1


def test_custom_create_scheduler_runs_only_on_first_verified_create(
        world, monkeypatch):
    client = _client(world)
    token = _token(world, "admin")
    calls = []

    class FakeScheduler:
        def schedule_agent(self, agent_id, schedule_config):
            calls.append((agent_id, dict(schedule_config)))

    from core.scheduler import AgentScheduler

    monkeypatch.setattr(AgentScheduler, "get_instance", lambda: FakeScheduler())
    body = {
        "name": "Scheduled Create",
        "category": "operations",
        "configuration": {},
        "schedule_config": {"active": True, "cron": "0 * * * *"},
    }
    operation_id = "scheduled-create"
    first_response = _post(client, token, body, operation_id=operation_id)
    assert first_response.status_code == 201, first_response.text
    replay = _post(client, token, body, operation_id=operation_id)
    assert replay.status_code == 201, replay.text
    assert len(calls) == 1

    changed = dict(body)
    changed["schedule_config"] = {"active": True, "cron": "1 * * * *"}
    conflict = _post(client, token, changed, operation_id=operation_id)
    assert conflict.status_code == 409, conflict.text
    assert len(calls) == 1
