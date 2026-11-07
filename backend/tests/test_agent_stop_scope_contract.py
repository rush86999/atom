"""Failure-first contracts for scoped, receipted agent stop/cancel."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

import core.agent_decision_write_service as service
import core.agent_task_registry as registry_module
from api.agent_routes import router as agent_router
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import AgentRegistry, AuditLog, Tenant, User, Workspace


class FakeTaskRegistry:
    def __init__(self):
        self.tasks = {}
        self.cancel_calls = []

    def get_agent_tasks(self, agent_id):
        return list(self.tasks.get(str(agent_id), []))

    async def cancel_agent_tasks(self, agent_id):
        self.cancel_calls.append(str(agent_id))
        return len(self.tasks.pop(str(agent_id), []))


@pytest.fixture()
def env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path}/agent-stop.db",
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
        User(id="admin-1", tenant_id="t1", workspace_id="ws1",
             email="admin@example.com", first_name="A", last_name="One",
             role="admin", status="active", is_active=True),
        User(id="admin-2", tenant_id="t2", workspace_id="ws3",
             email="admin2@example.com", first_name="A", last_name="Two",
             role="admin", status="active", is_active=True),
    ])
    seed.add_all([
        AgentRegistry(
            id="a1", name="Agent One", description="first",
            category="operations", module_path="agents.one",
            class_name="AgentOne", status="student",
            capabilities=[], promotion_episode_floor=None,
            tenant_id="t1", workspace_id="ws1", configuration={},
            schedule_config={}, enabled=True),
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

    fake = FakeTaskRegistry()
    fake.tasks["a1"] = [SimpleNamespace(task_id="t1"), SimpleNamespace(task_id="t2")]
    fake.tasks["a2"] = [SimpleNamespace(task_id="t3")]
    monkeypatch.setattr(registry_module, "agent_task_registry", fake)

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
        for key in ("member-1", "admin-1", "admin-2")
    }
    yield SimpleNamespace(
        engine=engine, Session=Session, app=app, client=client,
        actors=actors, monkeypatch=monkeypatch, fake=fake,
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


def _stop(env, user_id, agent_id, operation_id=None):
    suffix = f"?operation_id={operation_id}" if operation_id else ""
    return env.client(env.actors[user_id]).post(
        f"/api/agents/{agent_id}/stop{suffix}")


def test_member_stops_own_agent_and_writes_receipt(env):
    response = _stop(env, "member-1", "a1", "stop-one")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["agent_id"] == "a1"
    assert data["cancelled_tasks"] == 2
    assert data["verification"]["status"] == "verified"
    assert env.fake.cancel_calls == ["a1"]
    assert env.fake.tasks.get("a1") in (None, [])

    audits = _audits(env, "agent:stop:stop-one")
    assert len(audits) == 1
    audit = audits[0]
    assert audit.action == "agent_stopped"
    metadata = json.loads(audit.metadata_json)
    assert metadata["target_id"] == "a1"
    assert metadata["extra"]["cancelled_tasks"] == 2


def test_cross_tenant_and_cross_workspace_stop_refused(env):
    member = env.client(env.actors["member-1"])
    assert member.post(
        "/api/agents/a2/stop", json={}).status_code == 404
    assert member.post(
        "/api/agents/a3/stop", json={}).status_code == 404
    assert env.fake.cancel_calls == []
    assert _audits(env) == []

    admin = env.client(env.actors["admin-1"])
    allowed = admin.post(
        "/api/agents/a2/stop?operation_id=cross-ws", json={})
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["data"]["cancelled_tasks"] == 1
    foreign = env.client(env.actors["admin-2"]).post(
        "/api/agents/a1/stop", json={})
    assert foreign.status_code == 404, foreign.text


def test_no_tasks_is_no_change_without_receipt(env):
    env.fake.tasks.pop("a1", None)
    response = _stop(env, "admin-1", "a1", "no-tasks")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["verification"]["status"] == "no_change"
    assert data["verification"]["effect"] == "none"
    assert data["cancelled_tasks"] == 0
    assert env.fake.cancel_calls == []
    assert _audits(env) == []


def test_replay_does_not_cancel_new_tasks(env):
    first = _stop(env, "admin-1", "a1", "stop-replay")
    assert first.status_code == 200, first.text
    env.fake.tasks["a1"] = [SimpleNamespace(task_id="late")]
    replay = _stop(env, "admin-1", "a1", "stop-replay")
    assert replay.status_code == 200, replay.text
    data = replay.json()["data"]
    assert data["verification"]["status"] == "already_applied"
    assert data["cancelled_tasks"] == 2
    assert env.fake.cancel_calls == ["a1"]
    assert len(env.fake.tasks["a1"]) == 1
    assert len(_audits(env, "agent:stop:stop-replay")) == 1


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
    response = _stop(env, "member-1", "a1", "authority-stop")
    assert response.status_code in (401, 403, 409), response.text
    assert response.json()["detail"]["verification"]["effect"] == "none"
    assert env.fake.cancel_calls == []
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
                    AgentRegistry.id == "a1").values(
                        configuration={"peer": True}))
                peer.commit()
            finally:
                peer.close()
        return row

    env.monkeypatch.setattr(service, "_load_agent", load_then_change)
    response = _stop(env, "admin-1", "a1", "stale-stop")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "STALE_TARGET"
    assert env.fake.cancel_calls == []
    assert _audits(env) == []


def test_receipt_failure_reports_effect_unknown_after_cancel(env):
    original = service._audit_row

    def broken_audit(**kwargs):
        row = original(**kwargs)
        row.action = None
        return row

    env.monkeypatch.setattr(service, "_audit_row", broken_audit)
    response = _stop(env, "admin-1", "a1", "unknown-stop")
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "AGENT_EFFECT_UNKNOWN"
    assert detail["verification"]["effect"] == "unknown"
    assert detail["verification"]["replay"] == "do_not_repeat"
    # The known cancellation is preserved through the public error envelope.
    assert detail["data"] == {"agent_id": "a1", "cancelled_tasks": 2}
    assert env.fake.cancel_calls == ["a1"]
    assert _audits(env) == []


def test_readback_failure_reports_known_cancelled_count(env):
    original = service._verify_audit

    def refuted(*args, **kwargs):
        return {"status": "refuted", "audit_id": "agent:stop:unverified-stop"}

    env.monkeypatch.setattr(service, "_verify_audit", refuted)
    response = _stop(env, "admin-1", "a1", "unverified-stop")
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "AGENT_COMMITTED_UNVERIFIED"
    assert detail["verification"]["effect"] == "committed"
    assert detail["verification"]["replay"] == "do_not_repeat"
    assert detail["data"] == {"agent_id": "a1", "cancelled_tasks": 2}
    assert env.fake.cancel_calls == ["a1"]
    assert len(_audits(env, "agent:stop:unverified-stop")) == 1
    # Restore for any later assertion in this session.
    env.monkeypatch.setattr(service, "_verify_audit", original)


def test_unreadable_task_state_is_unavailable_before_dispatch(env):
    def unreadable(_agent_id):
        raise RuntimeError("synthetic registry read failure")

    env.monkeypatch.setattr(env.fake, "get_agent_tasks", unreadable)
    response = _stop(env, "admin-1", "a1", "unreadable-state")
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "AGENT_TASK_STATE_UNAVAILABLE"
    assert detail["verification"]["effect"] == "none"
    assert detail["verification"]["replay"] == "safe_after_refresh"
    assert env.fake.cancel_calls == []
    assert len(env.fake.tasks["a1"]) == 2
    assert _audits(env) == []


def test_cancellation_exception_after_dispatch_is_effect_unknown(env):
    async def partial_then_raise(agent_id):
        env.fake.cancel_calls.append(agent_id)
        env.fake.tasks[agent_id].pop()
        raise RuntimeError("synthetic failure after one cancellation")

    env.monkeypatch.setattr(
        env.fake, "cancel_agent_tasks", partial_then_raise)
    response = _stop(env, "admin-1", "a1", "partial-cancel")
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "AGENT_EFFECT_UNKNOWN"
    assert detail["verification"]["effect"] == "unknown"
    assert detail["verification"]["replay"] == "do_not_repeat"
    assert detail["verification"]["error"] == "CANCEL_CONFIRMATION_UNKNOWN"
    # Never invent a count from an exception; preserve only the known target.
    assert detail.get("data") == {"agent_id": "a1"}
    assert "cancelled_tasks" not in detail.get("data", {})
    assert len(env.fake.tasks["a1"]) == 1
    assert env.fake.cancel_calls == ["a1"]
    assert _audits(env) == []


def test_missing_agent_is_not_found(env):
    response = _stop(env, "admin-1", "missing", "missing-stop")
    assert response.status_code == 404, response.text
    assert env.fake.cancel_calls == []
    assert _audits(env) == []
