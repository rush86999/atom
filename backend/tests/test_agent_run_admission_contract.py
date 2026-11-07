"""Failure-first contracts for controlled agent-run admission."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

import api.agent_routes as agent_routes
import core.agent_decision_write_service as service
from api.agent_routes import router as agent_router
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import (
    AgentJob,
    AgentRegistry,
    AuditLog,
    Tenant,
    User,
    Workspace,
)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path}/agent-run.db",
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
        User(id="member-1", tenant_id="t1", workspace_id="ws1",
             email="member@example.com", first_name="M", last_name="One",
             role="member", status="active", is_active=True),
        User(id="lead-1", tenant_id="t1", workspace_id="ws1",
             email="lead@example.com", first_name="L", last_name="One",
             role="team_lead", status="active", is_active=True),
        User(id="admin-1", tenant_id="t1", workspace_id="ws1",
             email="admin@example.com", first_name="A", last_name="One",
             role="admin", status="active", is_active=True),
        User(id="wsa-1", tenant_id="t1", workspace_id="ws1",
             email="wsa@example.com", first_name="W", last_name="One",
             role="workspace_admin", status="active", is_active=True),
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
            configuration={"secret": "RUN-SECRET"}, enabled=True),
        AgentRegistry(
            id="a2", name="Agent Two", description="second",
            category="operations", module_path="agents.two",
            class_name="AgentTwo", status="student",
            capabilities=[], promotion_episode_floor=None,
            tenant_id="t1", workspace_id="ws2", configuration={},
            enabled=True),
        AgentRegistry(
            id="a3", name="Agent Three", description="third",
            category="operations", module_path="agents.three",
            class_name="AgentThree", status="student",
            capabilities=[], promotion_episode_floor=None,
            tenant_id="t2", workspace_id="ws3", configuration={},
            enabled=True),
        AgentRegistry(
            id="a-deprecated", name="Deprecated", description="dep",
            category="operations", module_path="agents.dep",
            class_name="Dep", status="deprecated",
            capabilities=[], promotion_episode_floor=None,
            tenant_id="t1", workspace_id="ws1", configuration={},
            enabled=True),
        AgentRegistry(
            id="a-paused", name="Paused", description="pause",
            category="operations", module_path="agents.pause",
            class_name="Pause", status="paused",
            capabilities=[], promotion_episode_floor=None,
            tenant_id="t1", workspace_id="ws1", configuration={},
            enabled=True),
        AgentRegistry(
            id="a-running", name="Running", description="run",
            category="operations", module_path="agents.running",
            class_name="Running", status="running",
            capabilities=[], promotion_episode_floor=None,
            tenant_id="t1", workspace_id="ws1", configuration={},
            enabled=True),
    ])
    seed.commit()
    seed.close()

    dispatch_calls = []

    async def default_dispatch(agent_id, parameters, execution_context=None):
        dispatch_calls.append((agent_id, dict(parameters)))
        assert execution_context and execution_context.get("job_id")
        return {"status": "success", "final_output": "stub"}

    monkeypatch.setattr(
        agent_routes, "execute_agent_task", default_dispatch)

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
        for key in ("member-1", "lead-1", "admin-1", "wsa-1", "admin-2")
    }
    yield SimpleNamespace(
        engine=engine, Session=Session, app=app, client=client,
        actors=actors, monkeypatch=monkeypatch,
        dispatch_calls=dispatch_calls,
    )


def _agent(env, agent_id):
    db = env.Session()
    try:
        return db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id).first()
    finally:
        db.close()


def _jobs(env, agent_id=None):
    db = env.Session()
    try:
        query = db.query(AgentJob)
        if agent_id is not None:
            query = query.filter(AgentJob.agent_id == agent_id)
        return query.all()
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


def _run(env, user_id, agent_id, operation_id=None, parameters=None):
    suffix = f"?operation_id={operation_id}" if operation_id else ""
    return env.client(env.actors[user_id]).post(
        f"/api/agents/{agent_id}/run{suffix}",
        json={"parameters": parameters or {}})


def test_member_admits_own_agent_and_dispatch_completes(env):
    response = _run(
        env, "member-1", "a1", "run-one",
        {"task_input": "do it", "secret": "RUN-SECRET"})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["agent_id"] == "a1"
    assert data["job_id"]
    assert data["verification"]["status"] == "verified"

    jobs = _jobs(env, "a1")
    assert len(jobs) == 1
    assert jobs[0].id == data["job_id"]
    assert jobs[0].status == "success"
    assert _agent(env, "a1").status == "student"
    assert len(env.dispatch_calls) == 1

    audits = _audits(env, "agent:run:run-one")
    assert len(audits) == 1
    audit = audits[0]
    assert audit.action == "agent_run_admitted"
    assert audit.user_id == "member-1"
    metadata = json.loads(audit.metadata_json)
    assert metadata["target_id"] == "a1"
    assert metadata["extra"]["job_id"] == data["job_id"]
    assert "RUN-SECRET" not in audit.metadata_json


def test_member_cross_workspace_and_tenant_refused(env):
    member = env.client(env.actors["member-1"])
    assert member.post(
        "/api/agents/a2/run", json={"parameters": {}}).status_code == 404
    assert member.post(
        "/api/agents/a3/run", json={"parameters": {}}).status_code == 404
    assert _jobs(env) == []
    assert _audits(env) == []

    admin = env.client(env.actors["admin-1"])
    allowed = admin.post(
        "/api/agents/a2/run?operation_id=cross-ws",
        json={"parameters": {"task_input": "ok"}})
    assert allowed.status_code == 200, allowed.text
    foreign = env.client(env.actors["admin-2"]).post(
        "/api/agents/a1/run", json={"parameters": {}})
    assert foreign.status_code == 404, foreign.text
    assert _agent(env, "a1") is not None


def test_deprecated_paused_and_running_refused(env):
    client = env.client(env.actors["admin-1"])
    deprecated = client.post(
        "/api/agents/a-deprecated/run", json={"parameters": {}})
    assert deprecated.status_code == 400, deprecated.text
    assert "AGENT_INVALID_STATE" in deprecated.text
    paused = client.post(
        "/api/agents/a-paused/run", json={"parameters": {}})
    assert paused.status_code == 400, paused.text
    running = client.post(
        "/api/agents/a-running/run", json={"parameters": {}})
    assert running.status_code == 409, running.text
    assert "ALREADY_RUNNING" in running.text
    assert _jobs(env) == []
    assert _audits(env) == []


def test_active_job_blocks_second_admission(env):
    db = env.Session()
    db.add(AgentJob(id="job-active", agent_id="a1", status="running"))
    db.commit()
    db.close()
    response = _run(env, "admin-1", "a1", "active-job")
    assert response.status_code == 409, response.text
    assert "ALREADY_RUNNING" in response.text
    assert len(_jobs(env, "a1")) == 1
    assert _audits(env) == []


def test_target_change_before_claim_refuses(env):
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
    response = _run(env, "admin-1", "a1", "stale-run")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "STALE_TARGET"
    assert _agent(env, "a1").name == "Peer Rename"
    assert _agent(env, "a1").status == "student"
    assert _jobs(env) == []
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
                    if change == "deactivate" else {"role": "guest"})
                peer.execute(update(User).where(
                    User.id == "member-1").values(**values))
                peer.commit()
            finally:
                peer.close()
        return row

    env.monkeypatch.setattr(service, "_load_agent", load_then_change)
    response = _run(env, "member-1", "a1", "authority-run")
    assert response.status_code in (401, 403, 409), response.text
    assert response.json()["detail"]["verification"]["effect"] == "none"
    assert _agent(env, "a1").status == "student"
    assert _jobs(env) == []
    assert _audits(env) == []


def test_replay_same_operation_no_second_dispatch(env):
    first = _run(
        env, "admin-1", "a1", "run-replay",
        {"task_input": "same"})
    assert first.status_code == 200, first.text
    replay = _run(
        env, "admin-1", "a1", "run-replay",
        {"task_input": "same"})
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["verification"]["status"] == "already_applied"
    assert len(_jobs(env, "a1")) == 1
    assert len(_audits(env, "agent:run:run-replay")) == 1
    assert len(env.dispatch_calls) == 1

    changed = _run(
        env, "admin-1", "a1", "run-replay",
        {"task_input": "different"})
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"]["error"]["code"] == (
        "OPERATION_CONFLICT")
    assert len(_jobs(env, "a1")) == 1


def test_audit_rollback_preserves_agent_and_job(env):
    original = service._audit_row

    def broken_audit(**kwargs):
        row = original(**kwargs)
        row.action = None
        return row

    env.monkeypatch.setattr(service, "_audit_row", broken_audit)
    response = _run(env, "admin-1", "a1", "rollback-run")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == (
        "AGENT_TRANSACTION_ROLLED_BACK")
    assert _agent(env, "a1").status == "student"
    assert _jobs(env) == []
    assert _audits(env) == []


def test_readback_failure_is_committed_unverified(env):
    env.monkeypatch.setattr(
        service, "_run_target_check",
        lambda db: (lambda *args, **kwargs: False))
    response = _run(env, "admin-1", "a1", "readback-run")
    assert response.status_code == 503, response.text
    assert response.json()["detail"]["error"]["code"] == (
        "AGENT_COMMITTED_UNVERIFIED")
    jobs = _jobs(env, "a1")
    assert len(jobs) == 1
    assert _agent(env, "a1").status == "running"
    assert len(_audits(env, "agent:run:readback-run")) == 1
    assert len(env.dispatch_calls) == 0


def test_execution_failure_marks_job_failed_and_restores_status(env):
    async def failing_dispatch(agent_id, parameters, execution_context=None):
        env.dispatch_calls.append((agent_id, dict(parameters)))
        raise RuntimeError("stub execution failure")

    env.monkeypatch.setattr(
        agent_routes, "execute_agent_task", failing_dispatch)
    response = _run(
        env, "admin-1", "a1", "failed-run",
        {"sync": True, "task_input": "fail"})
    assert response.status_code == 500, response.text
    jobs = _jobs(env, "a1")
    assert len(jobs) == 1
    assert jobs[0].status == "failed"
    assert _agent(env, "a1").status == "student"
    assert len(_audits(env, "agent:run:failed-run")) == 1


def test_sync_run_returns_stub_result_and_success_job(env):
    response = _run(
        env, "admin-1", "a1", "sync-run",
        {"sync": True, "task_input": "ok"})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["result"]["final_output"] == "stub"
    jobs = _jobs(env, "a1")
    assert jobs[0].status == "success"
    assert _agent(env, "a1").status == "student"
    assert len(env.dispatch_calls) == 1
