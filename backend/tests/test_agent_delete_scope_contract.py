"""Failure-first contracts for scoped, verified agent deletion."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

import core.agent_decision_write_service as service
from api.agent_routes import router as agent_router
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import (
    AgentEpisode,
    AgentJob,
    AgentRegistry,
    AuditLog,
    RuntimeSetting,
    Tenant,
    User,
    Workspace,
)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path}/agent-delete.db",
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
        User(id="wsa-2", tenant_id="t1", workspace_id="ws2",
             email="wsa2@example.com", first_name="W", last_name="B",
             role="workspace_admin", status="active", is_active=True),
        User(id="admin-1", tenant_id="t1", workspace_id="ws1",
             email="admin@example.com", first_name="A", last_name="One",
             role="admin", status="active", is_active=True),
        User(id="lead-1", tenant_id="t1", workspace_id="ws1",
             email="lead@example.com", first_name="L", last_name="One",
             role="team_lead", status="active", is_active=True),
        User(id="member-1", tenant_id="t1", workspace_id="ws1",
             email="member@example.com", first_name="M", last_name="One",
             role="member", status="active", is_active=True),
        User(id="admin-2", tenant_id="t2", workspace_id="ws3",
             email="admin2@example.com", first_name="A", last_name="Two",
             role="admin", status="active", is_active=True),
    ])
    agents = [
        AgentRegistry(
            id="a1", name="Agent One", description="first",
            category="operations", module_path="agents.one",
            class_name="AgentOne", status="student",
            capabilities=["tool.one"], promotion_episode_floor=None,
            tenant_id="t1", workspace_id="ws1", configuration={"secret": "S1"},
            enabled=True),
        AgentRegistry(
            id="a2", name="Agent Two", description="second",
            category="operations", module_path="agents.two",
            class_name="AgentTwo", status="intern",
            capabilities=["tool.two"], promotion_episode_floor=2,
            tenant_id="t1", workspace_id="ws2", configuration={},
            enabled=True),
        AgentRegistry(
            id="a3", name="Agent Three", description="third",
            category="operations", module_path="agents.three",
            class_name="AgentThree", status="student",
            capabilities=["tool.three"], promotion_episode_floor=None,
            tenant_id="t2", workspace_id="ws3", configuration={},
            enabled=True),
        AgentRegistry(
            id="a-keep", name="Keep Agent", description="keep",
            category="operations", module_path="agents.keep",
            class_name="KeepAgent", status="student",
            capabilities=[], promotion_episode_floor=None,
            tenant_id="t1", workspace_id="ws1", configuration={},
            enabled=True),
        AgentRegistry(
            id="a-demo", name="Demo Agent", description="demo",
            category="system", module_path="agents.demo",
            class_name="DemoAgent", status="student",
            capabilities=[], promotion_episode_floor=None,
            tenant_id="t1", workspace_id="ws1",
            configuration={"demo_agent": True}, enabled=True),
        AgentRegistry(
            id="atom_main", name="Main Agent", description="main",
            category="system", module_path="agents.main",
            class_name="MainAgent", status="autonomous",
            capabilities=[], promotion_episode_floor=None,
            tenant_id="t1", workspace_id="ws1", configuration={},
            enabled=True),
    ]
    seed.add_all(agents)
    seed.add_all([
        AgentJob(agent_id="a1", status="completed", result_summary="done"),
        AgentJob(agent_id="a1", status="failed", result_summary="nope"),
        AgentEpisode(agent_id="a1", tenant_id="t1",
                     maturity_at_time="student", outcome="success",
                     task_description="delete contract episode"),
        AgentJob(agent_id="a-keep", status="completed",
                 result_summary="keep"),
    ])
    seed.commit()
    seed.close()

    monkeypatch.setattr(service, "_running_task_count", lambda _agent_id: 0)

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
        for key in ("wsa-1", "wsa-2", "admin-1", "lead-1", "member-1",
                    "admin-2")
    }
    yield SimpleNamespace(
        engine=engine, Session=Session, app=app, client=client,
        actors=actors, monkeypatch=monkeypatch,
    )


def _agent(env, agent_id):
    db = env.Session()
    try:
        return db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id).first()
    finally:
        db.close()


def _jobs(env, agent_id):
    db = env.Session()
    try:
        return db.query(AgentJob).filter(
            AgentJob.agent_id == agent_id).count()
    finally:
        db.close()


def _episodes(env, agent_id):
    db = env.Session()
    try:
        return db.query(AgentEpisode).filter(
            AgentEpisode.agent_id == agent_id).count()
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


def _delete(env, user_id, agent_id, operation_id=None):
    suffix = f"?operation_id={operation_id}" if operation_id else ""
    return env.client(env.actors[user_id]).delete(
        f"/api/agents/{agent_id}{suffix}")


def test_cross_tenant_and_cross_workspace_delete_is_not_found(env):
    wsa = env.client(env.actors["wsa-1"])
    foreign = wsa.delete("/api/agents/a3?operation_id=cross-tenant")
    assert foreign.status_code == 404, foreign.text
    cross_ws = wsa.delete("/api/agents/a2?operation_id=cross-ws")
    assert cross_ws.status_code == 404, cross_ws.text
    assert _agent(env, "a3") is not None
    assert _agent(env, "a2") is not None
    assert _audits(env) == []

    member = env.client(env.actors["member-1"]).delete("/api/agents/a1")
    assert member.status_code == 403, member.text
    lead = env.client(env.actors["lead-1"]).delete("/api/agents/a1")
    assert lead.status_code == 403, lead.text
    assert _agent(env, "a1") is not None

    # A same-workspace workspace_admin may delete its own agent; ADMIN+ may
    # cross workspaces inside the tenant.
    own = env.client(env.actors["wsa-2"]).delete(
        "/api/agents/a2?operation_id=own-ws")
    assert own.status_code == 200, own.text
    assert _agent(env, "a2") is None
    admin = env.client(env.actors["admin-1"]).delete(
        "/api/agents/a-keep?operation_id=cross-ws-admin")
    assert admin.status_code == 200, admin.text
    assert _agent(env, "a-keep") is None
    assert _agent(env, "a3") is not None


def test_admin_delete_cleans_dependents_and_writes_receipt(env):
    response = _delete(env, "admin-1", "a1", "delete-a1")
    assert response.status_code == 200, response.text
    body = response.json()
    data = body["data"]
    assert data["agent_id"] == "a1"
    assert data["rows_cleaned"]["agent_jobs"] == 2
    assert data["rows_cleaned"]["agent_episodes"] == 1
    assert data["verification"]["status"] == "verified"
    assert data["verification"]["effect"] == "committed"
    assert data["operation_id"] == "agent:delete:delete-a1"

    assert _agent(env, "a1") is None
    assert _jobs(env, "a1") == 0
    assert _episodes(env, "a1") == 0
    # Unrelated agent rows survive.
    assert _jobs(env, "a-keep") == 1

    audits = _audits(env, "agent:delete:delete-a1")
    assert len(audits) == 1
    audit = audits[0]
    assert audit.action == "agent_deleted"
    assert audit.event_type == "delete"
    assert audit.user_id == "admin-1"
    assert audit.tenant_id == "t1"
    assert audit.workspace_id is None
    metadata = json.loads(audit.metadata_json)
    assert metadata["target_id"] == "a1"
    assert metadata["target_tenant_id"] == "t1"
    assert metadata["target_workspace_id"] == "ws1"
    assert metadata["result_status"] == "deleted"
    assert metadata["extra"]["rows_cleaned"]["agent_jobs"] == 2
    assert "S1" not in audit.metadata_json


def test_stale_target_before_claim_refuses(env):
    original = service._load_agent
    changed = {"done": False}

    def load_then_change(db, agent_id):
        row = original(db, agent_id)
        if row is not None and agent_id == "a1" and not changed["done"]:
            changed["done"] = True
            peer = env.Session()
            try:
                peer.execute(update(AgentRegistry).where(
                    AgentRegistry.id == "a1").values(name="Peer Rename"))
                peer.commit()
            finally:
                peer.close()
        return row

    env.monkeypatch.setattr(service, "_load_agent", load_then_change)
    response = _delete(env, "admin-1", "a1", "stale-delete")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "STALE_TARGET"
    assert _agent(env, "a1").name == "Peer Rename"
    assert _jobs(env, "a1") == 2
    assert _audits(env) == []


@pytest.mark.parametrize("change", ["deactivate", "demote"])
def test_authority_change_before_claim_refuses(env, change):
    original = service._load_agent
    changed = {"done": False}

    def load_then_change(db, agent_id):
        row = original(db, agent_id)
        if row is not None and agent_id == "a1" and not changed["done"]:
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

    env.monkeypatch.setattr(service, "_load_agent", load_then_change)
    response = _delete(env, "admin-1", "a1", "authority-delete")
    assert response.status_code in (401, 403, 409), response.text
    assert response.json()["detail"]["verification"]["effect"] == "none"
    assert _agent(env, "a1") is not None
    assert _jobs(env, "a1") == 2
    assert _audits(env) == []


def test_replay_and_changed_target(env):
    first = _delete(env, "admin-1", "a1", "replay-delete")
    assert first.status_code == 200, first.text
    replay = _delete(env, "admin-1", "a1", "replay-delete")
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["verification"]["status"] == "already_applied"
    assert len(_audits(env, "agent:delete:replay-delete")) == 1

    conflict = _delete(env, "admin-1", "a-keep", "replay-delete")
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["error"]["code"] == (
        "OPERATION_CONFLICT")
    assert _agent(env, "a-keep") is not None


def test_audit_rollback_preserves_agent_and_dependents(env):
    original = service._audit_row

    def broken_audit(**kwargs):
        row = original(**kwargs)
        row.action = None
        return row

    env.monkeypatch.setattr(service, "_audit_row", broken_audit)
    response = _delete(env, "admin-1", "a1", "rollback-delete")
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "AGENT_TRANSACTION_ROLLED_BACK"
    assert detail["verification"]["effect"] == "none"
    assert _agent(env, "a1") is not None
    assert _jobs(env, "a1") == 2
    assert _episodes(env, "a1") == 1
    assert _audits(env) == []


def test_post_commit_readback_is_committed_unverified(env):
    env.monkeypatch.setattr(
        service, "_delete_target_check",
        lambda db: (lambda *args, **kwargs: False))
    response = _delete(env, "admin-1", "a1", "readback-delete")
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "AGENT_COMMITTED_UNVERIFIED"
    assert detail["verification"]["effect"] == "committed"
    assert _agent(env, "a1") is None
    assert len(_audits(env, "agent:delete:readback-delete")) == 1


def test_lost_confirmation_is_effect_unknown(env):
    db = env.Session()
    try:
        def lost_commit():
            raise RuntimeError("lost confirmation AGENT-DELETE-SECRET")

        db.commit = lost_commit
        result = service.delete_agent(
            db, actor=env.actors["admin-1"], agent_id="a1",
            operation_id="lost-delete")
    finally:
        db.rollback()
        db.close()
    assert result["status"] == "effect_unknown"
    assert result["verification"]["effect"] == "unknown"
    assert result["verification"]["replay"] == "do_not_repeat"
    assert result["operation_id"] == "agent:delete:lost-delete"
    assert "AGENT-DELETE-SECRET" not in json.dumps(result)
    assert _agent(env, "a1") is not None
    assert _audits(env) == []


def test_main_agent_and_running_tasks_are_refused(env):
    main = _delete(env, "admin-1", "atom_main", "main-delete")
    assert main.status_code == 400, main.text
    assert "CANNOT_DELETE_MAIN_AGENT" in main.text
    assert _agent(env, "atom_main") is not None

    env.monkeypatch.setattr(
        service, "_running_task_count",
        lambda agent_id: 1 if agent_id == "a1" else 0)
    running = _delete(env, "admin-1", "a1", "running-delete")
    assert running.status_code == 400, running.text
    assert "AGENT_HAS_RUNNING_TASKS" in running.text
    assert _agent(env, "a1") is not None
    assert _audits(env) == []


def test_demo_tombstone_is_durable_across_replay(env):
    from core.admin_bootstrap import DEMO_AGENT_TOMBSTONE_KEY

    first = _delete(env, "admin-1", "a-demo", "demo-delete")
    assert first.status_code == 200, first.text
    assert first.json()["data"]["demo_tombstone"] is True
    db = env.Session()
    try:
        tombstone = db.query(RuntimeSetting).filter(
            RuntimeSetting.key == DEMO_AGENT_TOMBSTONE_KEY).one()
        assert tombstone.value_json["agent_id"] == "a-demo"
    finally:
        db.close()

    replay = _delete(env, "admin-1", "a-demo", "demo-delete")
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["verification"]["status"] == "already_applied"
    assert replay.json()["data"]["demo_tombstone"] is True


def test_wrong_audit_receipt_never_verifies(env):
    original = service._audit_row

    def wrong_audit(**kwargs):
        row = original(**kwargs)
        row.action = "wrong_action"
        return row

    env.monkeypatch.setattr(service, "_audit_row", wrong_audit)
    response = _delete(env, "admin-1", "a1", "tamper-delete")
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "AGENT_COMMITTED_UNVERIFIED"
    assert _agent(env, "a1") is None
    assert len(_audits(env, "agent:delete:tamper-delete")) == 1
