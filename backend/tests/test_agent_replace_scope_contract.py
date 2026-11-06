"""Failure-first contracts for scoped, verified agent replacement (PUT)."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, null, update
from sqlalchemy.orm import sessionmaker

import core.agent_decision_write_service as service
from api.agent_routes import router as agent_router
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import AgentRegistry, AuditLog, Tenant, User, Workspace


@pytest.fixture()
def env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path}/agent-replace.db",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    seed = Session()
    seed.add_all([
        Tenant(id="t1", name="Tenant One", subdomain="tenant-one"),
        Tenant(id="t2", name="Tenant Two", subdomain="tenant-two"),
        Workspace(id="ws1", name="Workspace One", tenant_id="t1"),
        Workspace(id="ws2", name="Workspace Two", tenant_id="t1"),
        Workspace(id="ws3", name="Workspace Three", tenant_id="t2"),
        User(id="wsa-1", tenant_id="t1", workspace_id="ws1",
             email="wsa@example.com", first_name="W", last_name="A",
             role="workspace_admin", status="active", is_active=True),
        User(id="admin-1", tenant_id="t1", workspace_id="ws1",
             email="admin@example.com", first_name="A", last_name="One",
             role="admin", status="active", is_active=True),
        User(id="member-1", tenant_id="t1", workspace_id="ws1",
             email="member@example.com", first_name="M", last_name="One",
             role="member", status="active", is_active=True),
        User(id="admin-2", tenant_id="t2", workspace_id="ws3",
             email="admin2@example.com", first_name="A", last_name="Two",
             role="admin", status="active", is_active=True),
    ])
    seed.add_all([
        AgentRegistry(
            id="a1", name="Agent One", description="first",
            category="operations", module_path="agents.one",
            class_name="AgentOne", status="student",
            capabilities=["tool.one"], promotion_episode_floor=None,
            tenant_id="t1", workspace_id="ws1",
            configuration={"secret": "REPLACE-SECRET"},
            schedule_config={"active": False}, enabled=True),
        AgentRegistry(
            id="a2", name="Agent Two", description="second",
            category="operations", module_path="agents.two",
            class_name="AgentTwo", status="student",
            capabilities=[], promotion_episode_floor=None,
            tenant_id="t1", workspace_id="ws2", configuration={},
            schedule_config={}, enabled=True),
        AgentRegistry(
            id="a3", name="Agent Three", description="third",
            category="operations", module_path="agents.three",
            class_name="AgentThree", status="student",
            capabilities=[], promotion_episode_floor=None,
            tenant_id="t2", workspace_id="ws3", configuration={},
            schedule_config={}, enabled=True),
    ])
    seed.commit()
    seed.close()

    scheduler_calls = []
    fake_scheduler = SimpleNamespace(
        schedule_agent=lambda agent_id, config: scheduler_calls.append(
            (agent_id, dict(config or {}))))
    import core.scheduler as scheduler_module
    monkeypatch.setattr(
        scheduler_module.AgentScheduler, "get_instance",
        lambda: fake_scheduler)

    app = FastAPI()
    app.include_router(agent_router)

    def db_override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = db_override

    def client(user: User):
        scoped = FastAPI()
        scoped.include_router(agent_router)
        scoped.dependency_overrides[get_db] = db_override
        scoped.dependency_overrides[get_current_user] = lambda: user
        return TestClient(scoped, raise_server_exceptions=False)

    actors = {
        key: Session().query(User).filter(User.id == key).one()
        for key in ("wsa-1", "admin-1", "member-1", "admin-2")
    }
    yield SimpleNamespace(
        engine=engine, Session=Session, app=app, client=client,
        actors=actors, monkeypatch=monkeypatch,
        scheduler_calls=scheduler_calls,
    )


def _agent(env, agent_id):
    db = env.Session()
    try:
        return db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id).first()
    finally:
        db.close()


def _audits(env, operation_id=None):
    db = env.Session()
    try:
        query = db.query(AuditLog)
        if operation_id is not None:
            query = query.filter(AuditLog.id == operation_id)
        return query.all()
    finally:
        db.close()


def _put(env, user_id, agent_id, operation_id=None, **body):
    suffix = f"?operation_id={operation_id}" if operation_id else ""
    payload = {
        "name": "Replaced Agent",
        "category": "replacement",
        "description": "replaced",
    }
    payload.update(body)
    return env.client(env.actors[user_id]).put(
        f"/api/agents/{agent_id}{suffix}", json=payload)


def test_cross_tenant_and_cross_workspace_replace_is_not_found(env):
    wsa = env.client(env.actors["wsa-1"])
    foreign = wsa.put(
        "/api/agents/a3", json={"name": "X", "category": "Y"})
    assert foreign.status_code == 404, foreign.text
    cross_ws = wsa.put(
        "/api/agents/a2", json={"name": "X", "category": "Y"})
    assert cross_ws.status_code == 404, cross_ws.text
    member = env.client(env.actors["member-1"]).put(
        "/api/agents/a1", json={"name": "X", "category": "Y"})
    assert member.status_code == 403, member.text
    assert _agent(env, "a1").name == "Agent One"
    assert _agent(env, "a2").name == "Agent Two"
    assert _agent(env, "a3").name == "Agent Three"
    assert _audits(env) == []

    admin = env.client(env.actors["admin-1"]).put(
        "/api/agents/a2?operation_id=cross-ws",
        json={"name": "Cross WS", "category": "replacement"})
    assert admin.status_code == 200, admin.text
    foreign_admin = env.client(env.actors["admin-2"]).put(
        "/api/agents/a1", json={"name": "X", "category": "Y"})
    assert foreign_admin.status_code == 404, foreign_admin.text


def test_replace_agent_persists_fields_and_receipt(env):
    response = _put(
        env, "admin-1", "a1", "replace-one",
        description="new description", category="finance",
        configuration={"model": "gpt-4o", "secret": "REPLACE-SECRET"},
        schedule_config={"active": True, "cron": "0 9 * * *"})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["agent_id"] == "a1"

    row = _agent(env, "a1")
    assert row.name == "Replaced Agent"
    assert row.description == "new description"
    assert row.category == "finance"
    assert row.configuration["model"] == "gpt-4o"
    assert row.schedule_config["active"] is True
    assert len(env.scheduler_calls) == 1
    assert env.scheduler_calls[0][0] == "a1"

    audits = _audits(env, "agent:replace:replace-one")
    assert len(audits) == 1
    audit = audits[0]
    assert audit.action == "agent_replaced"
    metadata = json.loads(audit.metadata_json)
    assert metadata["target_id"] == "a1"
    assert "REPLACE-SECRET" not in audit.metadata_json
    assert "0 9 * * *" not in audit.metadata_json


def test_stale_target_before_claim_refuses(env):
    original = service._load_replace_source
    changed = {"done": False}

    def load_then_change(db, agent_id):
        row = original(db, agent_id)
        if row[0] is not None and agent_id == "a1" and not changed["done"]:
            changed["done"] = True
            peer = env.Session()
            try:
                peer.execute(update(AgentRegistry).where(
                    AgentRegistry.id == "a1").values(
                        configuration={"peer": True}))
                peer.commit()
            finally:
                peer.close()
        return row

    env.monkeypatch.setattr(
        service, "_load_replace_source", load_then_change)
    response = _put(env, "admin-1", "a1", "stale-replace")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "STALE_TARGET"
    assert _agent(env, "a1").name == "Agent One"
    assert _agent(env, "a1").configuration == {"peer": True}
    assert _audits(env) == []


@pytest.mark.parametrize("change", ["deactivate", "demote"])
def test_authority_change_before_claim_refuses(env, change):
    original = service._load_replace_source
    changed = {"done": False}

    def load_then_change(db, agent_id):
        row = original(db, agent_id)
        if row[0] is not None and agent_id == "a1" and not changed["done"]:
            changed["done"] = True
            peer = env.Session()
            try:
                values = (
                    {"status": "inactive", "is_active": False}
                    if change == "deactivate" else {"role": "member"})
                peer.execute(update(User).where(
                    User.id == "admin-1").values(**values))
                peer.commit()
            finally:
                peer.close()
        return row

    env.monkeypatch.setattr(
        service, "_load_replace_source", load_then_change)
    response = _put(env, "admin-1", "a1", "authority-replace")
    assert response.status_code in (401, 403, 409), response.text
    assert response.json()["detail"]["verification"]["effect"] == "none"
    assert _agent(env, "a1").name == "Agent One"
    assert _audits(env) == []


def test_replay_same_operation_and_changed_material(env):
    first = _put(env, "admin-1", "a1", "replay-replace")
    assert first.status_code == 200, first.text
    replay = _put(env, "admin-1", "a1", "replay-replace")
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["verification"]["status"] == "already_applied"
    assert len(_audits(env, "agent:replace:replay-replace")) == 1
    assert len(env.scheduler_calls) == 0

    changed = _put(
        env, "admin-1", "a1", "replay-replace", name="Different Name")
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"]["error"]["code"] == (
        "OPERATION_CONFLICT")


def test_audit_rollback_preserves_agent(env):
    original = service._audit_row

    def broken_audit(**kwargs):
        row = original(**kwargs)
        row.action = None
        return row

    env.monkeypatch.setattr(service, "_audit_row", broken_audit)
    response = _put(env, "admin-1", "a1", "rollback-replace")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == (
        "AGENT_TRANSACTION_ROLLED_BACK")
    assert _agent(env, "a1").name == "Agent One"
    assert _agent(env, "a1").configuration == {"secret": "REPLACE-SECRET"}
    assert _audits(env) == []


def test_readback_failure_is_committed_unverified(env):
    original = service._state_digest
    calls = {"n": 0}

    def failing_readback(material):
        calls["n"] += 1
        if calls["n"] >= 3:
            return "wrong-readback-digest"
        return original(material)

    env.monkeypatch.setattr(service, "_state_digest", failing_readback)
    response = _put(env, "admin-1", "a1", "readback-replace")
    assert response.status_code == 503, response.text
    assert response.json()["detail"]["error"]["code"] == (
        "AGENT_COMMITTED_UNVERIFIED")
    assert _agent(env, "a1").name == "Replaced Agent"
    assert len(_audits(env, "agent:replace:readback-replace")) == 1


def test_matching_replacement_is_no_change(env):
    existing = _agent(env, "a1")
    response = _put(
        env, "admin-1", "a1", "no-change",
        name=existing.name, description=existing.description,
        category=existing.category)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["verification"]["status"] == "no_change"
    assert data["verification"]["effect"] == "none"
    assert _audits(env) == []
    assert env.scheduler_calls == []


def test_missing_agent_is_not_found(env):
    response = _put(env, "admin-1", "missing", "missing-replace")
    assert response.status_code == 404, response.text
    assert _audits(env) == []


@pytest.mark.parametrize("fields", [
    ("configuration",),
    ("schedule_config",),
    ("configuration", "schedule_config"),
])
@pytest.mark.parametrize("storage", ["json", "sql"])
def test_unchanged_nullable_material_succeeds(env, fields, storage):
    """An unchanged nullable source field is not a concurrent target change."""
    with env.Session() as db:
        values = {
            field: (null() if storage == "sql" else None)
            for field in fields
        }
        db.execute(update(AgentRegistry).where(
            AgentRegistry.id == "a1").values(**values))
        db.commit()
    before = _agent(env, "a1")
    for field in fields:
        assert getattr(before, field) is None

    operation_id = f"nullable-{storage}-{'-'.join(fields)}"
    response = _put(
        env, "admin-1", "a1", operation_id,
        name="Updated existing agent", category="updated")
    assert response.status_code == 200, response.text
    row = _agent(env, "a1")
    assert row.name == "Updated existing agent"
    assert row.category == "updated"
    for field in fields:
        assert getattr(row, field) is None
    assert len(_audits(env, f"agent:replace:{operation_id}")) == 1
    assert env.scheduler_calls == []


def test_empty_object_nullable_material_succeeds(env):
    with env.Session() as db:
        db.execute(update(AgentRegistry).where(
            AgentRegistry.id == "a1").values(
                configuration={}, schedule_config={}))
        db.commit()
    response = _put(
        env, "admin-1", "a1", "empty-object",
        name="Updated existing agent", category="updated")
    assert response.status_code == 200, response.text
    row = _agent(env, "a1")
    assert row.configuration == {}
    assert row.schedule_config == {}
    assert len(_audits(env, "agent:replace:empty-object")) == 1
    assert env.scheduler_calls == []


def test_null_configuration_peer_change_refuses(env):
    with env.Session() as db:
        db.execute(update(AgentRegistry).where(
            AgentRegistry.id == "a1").values(
                configuration=None, schedule_config=None))
        db.commit()
    original = service._load_replace_source
    changed = {"done": False}

    def load_then_change(db, agent_id):
        row = original(db, agent_id)
        if row[0] is not None and not changed["done"]:
            changed["done"] = True
            peer = env.Session()
            try:
                peer.execute(update(AgentRegistry).where(
                    AgentRegistry.id == "a1").values(
                        configuration={"peer": True}))
                peer.commit()
            finally:
                peer.close()
        return row

    env.monkeypatch.setattr(
        service, "_load_replace_source", load_then_change)
    response = _put(env, "admin-1", "a1", "null-peer-change")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "STALE_TARGET"
    assert _agent(env, "a1").configuration == {"peer": True}
    assert _audits(env) == []
