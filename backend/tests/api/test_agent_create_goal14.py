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
