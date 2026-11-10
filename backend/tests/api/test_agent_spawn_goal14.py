"""Goal14 public spawned-agent create boundary controls.

Real scratch SQLite + real FastAPI route + real JWT. The Atom template and
shared create decision writer are real; no model/provider is called. The
persist=False branch is the real in-memory ephemeral path.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from api.agent_routes import router as agent_router
from core.atom_meta_agent import SpecialtyAgentTemplate
from core.auth import create_access_token
from core.database import Base, get_db
from core.models import AgentRegistry, AuditLog, Tenant, User, Workspace


@pytest.fixture
def world(tmp_path: Path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'spawn.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
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
            User(id="admin", tenant_id="company", workspace_id="ws-a",
                 email="admin@example.test", hashed_password="x",
                 first_name="A", last_name="D", role="workspace_admin",
                 status="active", is_active=True),
            User(id="member", tenant_id="company", workspace_id="ws-a",
                 email="member@example.test", hashed_password="x",
                 first_name="M", last_name="V", role="member",
                 status="active", is_active=True),
            User(id="foreign-admin", tenant_id="other", workspace_id="ws-b",
                 email="foreign-admin@example.test", hashed_password="x",
                 first_name="F", last_name="A", role="workspace_admin",
                 status="active", is_active=True),
            User(id="inactive", tenant_id="company", workspace_id="ws-a",
                 email="inactive@example.test", hashed_password="x",
                 first_name="I", last_name="V", role="workspace_admin",
                 status="inactive", is_active=False),
        ])
        db.add(AgentRegistry(
            id="atom_specialty_init", name="Specialty Init",
            category="System", module_path="core.atom_meta_agent",
            class_name="SpecialtyAgentTemplate", status="autonomous",
            confidence_score=0.9, role="agent", type="personal",
            tenant_id="company", workspace_id="ws-a",
            configuration={
                "capability_maturities": {
                    "finance_analyst": "AUTONOMOUS",
                },
            },
        ))
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


def _post(client, token, body, operation_id=None):
    url = "/api/agents/spawn"
    if operation_id is not None:
        url += f"?operation_id={operation_id}"
    return client.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )


def _audit_count(world, operation_id):
    with world["Session"]() as db:
        return db.query(func.count(AuditLog.id)).filter(
            AuditLog.id == f"agent:create:{operation_id}").scalar()


def _init_configuration(world):
    with world["Session"]() as db:
        return db.get(AgentRegistry, "atom_specialty_init").configuration


def test_spawn_persist_true_uses_caller_scope_and_exact_material(world):
    client = _client(world)
    token = _token(world, "admin")
    before_init = _init_configuration(world)
    response = _post(
        client, token,
        {"template": "finance_analyst", "persist": True},
        operation_id="spawn-op-1",
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["persisted"] is True
    assert data["operation_id"] == "agent:create:spawn-op-1"
    assert data["audit_id"] == "agent:create:spawn-op-1"
    assert data["verification"]["status"] == "verified"

    template = SpecialtyAgentTemplate.TEMPLATES["finance_analyst"]
    with world["Session"]() as db:
        agent = db.get(AgentRegistry, data["agent_id"])
        assert agent is not None
        assert agent.name == template["name"]
        assert agent.category == template["category"]
        assert agent.tenant_id == "company"
        assert agent.workspace_id == "ws-a"
        assert agent.status == "student"
        assert float(agent.confidence_score) == pytest.approx(0.35)
        assert agent.user_id == "admin"
        assert agent.parent_agent_id is None
        assert agent.capabilities == template["capabilities"]
        assert agent.configuration == template["default_params"]
        audit = db.get(AuditLog, "agent:create:spawn-op-1")
        assert audit is not None
        assert audit.action == "agent_created"
        assert audit.user_id == "admin"
        assert audit.tenant_id == "company"
        assert db.get(
            AgentRegistry, "atom_specialty_init").configuration == before_init


def test_spawn_distinct_operations_create_distinct_agents(world):
    client = _client(world)
    token = _token(world, "admin")
    body = {"template": "finance_analyst", "persist": True}
    first = _post(client, token, body, operation_id="spawn-distinct-a")
    second = _post(client, token, body, operation_id="spawn-distinct-b")
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    first_id = first.json()["data"]["agent_id"]
    second_id = second.json()["data"]["agent_id"]
    assert first_id != second_id
    with world["Session"]() as db:
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.id.in_([first_id, second_id])).scalar() == 2
        assert db.query(func.count(AuditLog.id)).filter(
            AuditLog.id.in_([
                "agent:create:spawn-distinct-a",
                "agent:create:spawn-distinct-b",
            ])).scalar() == 2


def test_spawn_duplicate_exact_operation_is_idempotent(world):
    client = _client(world)
    token = _token(world, "admin")
    body = {"template": "finance_analyst", "persist": True}
    first = _post(client, token, body, operation_id="spawn-dup")
    assert first.status_code == 200, first.text
    agent_id = first.json()["data"]["agent_id"]
    replay = _post(client, token, body, operation_id="spawn-dup")
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["agent_id"] == agent_id
    assert replay.json()["data"]["verification"]["status"] == "already_applied"
    with world["Session"]() as db:
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.id == agent_id).scalar() == 1
        assert _audit_count(world, "spawn-dup") == 1


def test_spawn_changed_material_same_operation_conflicts(world):
    client = _client(world)
    token = _token(world, "admin")
    first = _post(client, token, {
        "template": "finance_analyst",
        "custom_params": {"focus": "cost"},
        "persist": True,
    }, operation_id="spawn-changed")
    assert first.status_code == 200, first.text
    agent_id = first.json()["data"]["agent_id"]
    changed = _post(client, token, {
        "template": "finance_analyst",
        "custom_params": {"focus": "growth"},
        "persist": True,
    }, operation_id="spawn-changed")
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"]["error"]["code"] == "OPERATION_CONFLICT"
    with world["Session"]() as db:
        assert db.get(AgentRegistry, agent_id).configuration == {"focus": "cost"}
        assert db.query(func.count(AuditLog.id)).filter(
            AuditLog.id == "agent:create:spawn-changed").scalar() == 1


def test_spawn_foreign_admin_uses_own_scope(world):
    client = _client(world)
    token = _token(world, "foreign-admin")
    response = _post(client, token, {
        "template": "finance_analyst", "persist": True,
    }, operation_id="spawn-foreign")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    with world["Session"]() as db:
        agent = db.get(AgentRegistry, data["agent_id"])
        assert agent.tenant_id == "other"
        assert agent.workspace_id == "ws-b"
        audit = db.get(AuditLog, "agent:create:spawn-foreign")
        assert audit.tenant_id == "other"
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.tenant_id == "company",
            AgentRegistry.name == "Finance Analyst",
        ).scalar() == 0


def test_spawn_custom_params_cannot_forge_authority(world):
    client = _client(world)
    token = _token(world, "admin")
    forged = {
        "name": "Forged Spawn",
        "category": "Operations",
        "description": "forged material",
        "capabilities": ["read"],
        "configuration": {"x": 1},
        "status": "autonomous",
        "maturity": "autonomous",
        "confidence_score": 0.99,
        "tenant_id": "other",
        "workspace_id": "ws-b",
        "user_id": "foreign",
        "parent_agent_id": "foreign-agent",
    }
    response = _post(client, token, {
        "template": "custom",
        "custom_params": forged,
        "persist": True,
    }, operation_id="spawn-forged")
    assert response.status_code == 200, response.text
    with world["Session"]() as db:
        agent = db.get(AgentRegistry, response.json()["data"]["agent_id"])
        assert agent.name == "Forged Spawn"
        assert agent.category == "Operations"
        assert agent.status == "student"
        assert float(agent.confidence_score) == pytest.approx(0.35)
        assert agent.tenant_id == "company"
        assert agent.workspace_id == "ws-a"
        assert agent.user_id == "admin"
        assert agent.parent_agent_id is None
        assert agent.capabilities == ["read"]


def test_spawn_concurrent_authority_change_is_refused(world, monkeypatch):
    from core import agent_decision_write_service as writes

    original = writes._claim_actor

    def claim_after_demotion(db, actor):
        with world["Session"]() as peer:
            user = peer.get(User, "admin")
            user.role = "member"
            peer.commit()
        return original(db, actor)

    monkeypatch.setattr(writes, "_claim_actor", claim_after_demotion)
    client = _client(world)
    token = _token(world, "admin")
    response = _post(client, token, {
        "template": "finance_analyst", "persist": True,
    }, operation_id="spawn-race")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "AUTHORITY_CHANGED"
    with world["Session"]() as db:
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.name == "Finance Analyst").scalar() == 0
        assert db.get(AuditLog, "agent:create:spawn-race") is None


def test_spawn_inactive_or_member_is_forbidden(world):
    client = _client(world)
    for user_id in ("inactive", "member"):
        response = _post(
            client, _token(world, user_id),
            {"template": "finance_analyst", "persist": True},
            operation_id=f"spawn-{user_id}",
        )
        assert response.status_code in (401, 403), response.text
    with world["Session"]() as db:
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.name == "Finance Analyst").scalar() == 0
        assert db.query(func.count(AuditLog.id)).filter(
            AuditLog.id.in_([
                "agent:create:spawn-inactive",
                "agent:create:spawn-member",
            ])).scalar() == 0


def test_spawn_null_and_empty_template_material_is_exact(
        world, monkeypatch):
    monkeypatch.setitem(SpecialtyAgentTemplate.TEMPLATES, "test_spawn_null", {
        "name": "Null Config Spawn",
        "category": "Operations",
        "description": "null config",
        "capabilities": ["read"],
        "default_params": None,
    })
    monkeypatch.setitem(SpecialtyAgentTemplate.TEMPLATES, "test_spawn_empty", {
        "name": "Empty Config Spawn",
        "category": "Operations",
        "description": "empty config",
        "capabilities": ["read"],
        "default_params": {},
    })
    client = _client(world)
    token = _token(world, "admin")
    null_body = {"template": "test_spawn_null", "persist": True}
    null_response = _post(
        client, token, null_body, operation_id="spawn-null")
    assert null_response.status_code == 200, null_response.text
    null_id = null_response.json()["data"]["agent_id"]
    with world["Session"]() as db:
        assert db.get(AgentRegistry, null_id).configuration is None
        assert db.get(AgentRegistry, null_id).schedule_config is None

    replay = _post(client, token, null_body, operation_id="spawn-null")
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["verification"]["status"] == "already_applied"

    changed = _post(client, token, {
        "template": "test_spawn_empty", "persist": True,
    }, operation_id="spawn-null")
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"]["error"]["code"] == "OPERATION_CONFLICT"
    with world["Session"]() as db:
        assert db.get(AgentRegistry, null_id).configuration is None
        assert _audit_count(world, "spawn-null") == 1


def test_spawn_rollback_and_readback_uncertainty(world, monkeypatch):
    import uuid

    client = _client(world)
    token = _token(world, "admin")
    # PK conflict at commit forces a real rollback: no child/audit is written
    # and the existing row is untouched.
    target_id = str(uuid.uuid5(
        uuid.NAMESPACE_URL, "agent:create:spawn-rollback"))
    with world["Session"]() as db:
        db.add(AgentRegistry(
            id=target_id, name="Existing Rollback", category="Operations",
            module_path="tests.spawn", class_name="Existing",
            status="student", confidence_score=0.2,
            tenant_id="company", workspace_id="ws-a",
        ))
        db.commit()
    response = _post(client, token, {
        "template": "finance_analyst", "persist": True,
    }, operation_id="spawn-rollback")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == (
        "AGENT_TRANSACTION_ROLLED_BACK")
    with world["Session"]() as db:
        assert db.get(AgentRegistry, target_id).name == "Existing Rollback"
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.name == "Finance Analyst").scalar() == 0
        assert db.get(AuditLog, "agent:create:spawn-rollback") is None

    import core.agent_decision_write_service as writes

    monkeypatch.setattr(writes, "_load_agent", lambda db, agent_id: None)
    unverified = _post(client, token, {
        "template": "finance_analyst", "persist": True,
    }, operation_id="spawn-readback")
    assert unverified.status_code == 503, unverified.text
    assert unverified.json()["detail"]["error"]["code"] == (
        "AGENT_COMMITTED_UNVERIFIED")
    with world["Session"]() as db:
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.name == "Finance Analyst").scalar() == 1
        assert db.get(AuditLog, "agent:create:spawn-readback") is not None


def test_spawn_persist_false_is_honest_nondurable(world):
    client = _client(world)
    token = _token(world, "admin")
    before_init = _init_configuration(world)
    response = _post(client, token, {
        "template": "finance_analyst", "persist": False,
    }, operation_id="spawn-ephemeral")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["persisted"] is False
    assert data["verification"] == {
        "status": "not_persisted", "effect": "none",
    }
    assert "operation_id" not in data
    assert "audit_id" not in data
    with world["Session"]() as db:
        assert db.query(func.count(AgentRegistry.id)).filter(
            AgentRegistry.name == "Finance Analyst").scalar() == 0
        assert db.query(func.count(AuditLog.id)).filter(
            AuditLog.id == "agent:create:spawn-ephemeral").scalar() == 0
        assert db.get(
            AgentRegistry, "atom_specialty_init").configuration == before_init


def _personal_admin(world):
    with world["Session"]() as db:
        db.add(User(
            id="personal-admin", tenant_id=None, workspace_id=None,
            email="personal-admin@example.test", hashed_password="x",
            first_name="P", last_name="A", role="workspace_admin",
            status="active", is_active=True,
        ))
        db.commit()


def _capture_scoped_factory(monkeypatch):
    import core.atom_meta_agent as atom_mod

    captured = {}
    real = atom_mod.get_scoped_atom_agent

    def wrapped(workspace_id, tenant_id=None, user=None):
        captured["workspace_id"] = workspace_id
        captured["tenant_id"] = tenant_id
        return real(workspace_id, tenant_id, user)

    monkeypatch.setattr(atom_mod, "get_scoped_atom_agent", wrapped)
    return captured


def test_spawn_personal_scope_matches_shared_writer(world, monkeypatch):
    import core.personal_scope as scope

    monkeypatch.setattr(scope, "PERSONAL_WORKSPACE_ID", "personal-ws")
    monkeypatch.setattr(scope, "PERSONAL_TENANT_ID", "personal-tenant")
    _personal_admin(world)
    captured = _capture_scoped_factory(monkeypatch)
    client = _client(world)
    token = _token(world, "personal-admin")
    response = _post(client, token, {
        "template": "finance_analyst", "persist": True,
    }, operation_id="spawn-personal")
    assert response.status_code == 200, response.text
    agent_id = response.json()["data"]["agent_id"]
    with world["Session"]() as db:
        agent = db.get(AgentRegistry, agent_id)
        assert agent.tenant_id == "personal-tenant"
        assert agent.workspace_id == "personal-ws"
    assert captured == {
        "workspace_id": "personal-ws",
        "tenant_id": "personal-tenant",
    }


def test_spawn_ephemeral_personal_scope_matches_writer(world, monkeypatch):
    import core.personal_scope as scope

    monkeypatch.setattr(scope, "PERSONAL_WORKSPACE_ID", "personal-ws")
    monkeypatch.setattr(scope, "PERSONAL_TENANT_ID", "personal-tenant")
    _personal_admin(world)
    captured = _capture_scoped_factory(monkeypatch)
    client = _client(world)
    token = _token(world, "personal-admin")
    response = _post(client, token, {
        "template": "finance_analyst", "persist": False,
    }, operation_id="spawn-personal-ephemeral")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["persisted"] is False
    assert captured == {
        "workspace_id": "personal-ws",
        "tenant_id": "personal-tenant",
    }
