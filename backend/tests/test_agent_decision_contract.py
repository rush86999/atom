"""Failure-first contracts for verified agent update/promote decisions."""
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
from core.models import AgentRegistry, AuditLog, Tenant, User, Workspace


@pytest.fixture()
def env(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/agent-decision.db",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    seed = Session()
    tenants = [
        Tenant(id="t1", name="Tenant One", subdomain="tenant-one"),
        Tenant(id="t2", name="Tenant Two", subdomain="tenant-two"),
    ]
    workspaces = [
        Workspace(id="ws1", name="Workspace One", tenant_id="t1"),
        Workspace(id="ws2", name="Workspace Two", tenant_id="t1"),
        Workspace(id="ws3", name="Workspace Three", tenant_id="t2"),
    ]
    users = [
        User(
            id="wsa-1", tenant_id="t1", workspace_id="ws1",
            email="wsa@example.com", first_name="Workspace",
            last_name="Admin", role="workspace_admin", status="active",
            is_active=True),
        User(
            id="admin-1", tenant_id="t1", workspace_id="ws1",
            email="admin@example.com", first_name="Admin",
            last_name="One", role="admin", status="active",
            is_active=True),
        User(
            id="member-1", tenant_id="t1", workspace_id="ws1",
            email="member@example.com", first_name="Member",
            last_name="One", role="member", status="active",
            is_active=True),
        User(
            id="lead-1", tenant_id="t1", workspace_id="ws1",
            email="lead@example.com", first_name="Lead",
            last_name="One", role="team_lead", status="active",
            is_active=True),
        User(
            id="admin-2", tenant_id="t2", workspace_id="ws3",
            email="admin2@example.com", first_name="Admin",
            last_name="Two", role="admin", status="active",
            is_active=True),
    ]
    agents = [
        AgentRegistry(
            id="a1", name="Agent One", description="first",
            category="operations", module_path="agents.one",
            class_name="AgentOne", status="student",
            capabilities=["tool.one"], promotion_episode_floor=None,
            tenant_id="t1", workspace_id="ws1"),
        AgentRegistry(
            id="a2", name="Agent Two", description="second",
            category="operations", module_path="agents.two",
            class_name="AgentTwo", status="intern",
            capabilities=["tool.two"], promotion_episode_floor=2,
            tenant_id="t1", workspace_id="ws2"),
        AgentRegistry(
            id="a3", name="Agent Three", description="third",
            category="operations", module_path="agents.three",
            class_name="AgentThree", status="student",
            capabilities=["tool.three"], promotion_episode_floor=None,
            tenant_id="t2", workspace_id="ws3"),
        AgentRegistry(
            id="a-legacy", name="Legacy Agent", description="legacy",
            category="operations", module_path="agents.legacy",
            class_name="LegacyAgent", status="student",
            capabilities=[], promotion_episode_floor=None),
    ]
    seed.add_all(tenants + workspaces + users + agents)
    seed.commit()
    seed.close()

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
        "wsa-1": Session().query(User).filter(User.id == "wsa-1").one(),
        "admin-1": Session().query(User).filter(User.id == "admin-1").one(),
        "member-1": Session().query(User).filter(User.id == "member-1").one(),
        "lead-1": Session().query(User).filter(User.id == "lead-1").one(),
        "admin-2": Session().query(User).filter(User.id == "admin-2").one(),
    }
    yield SimpleNamespace(
        engine=engine, Session=Session, app=app, client=client,
        actors=actors,
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


def _peer_update(env, agent_id, **values):
    db = env.Session()
    try:
        db.execute(update(AgentRegistry).where(
            AgentRegistry.id == agent_id).values(**values))
        db.commit()
    finally:
        db.close()


def test_workspace_admin_updates_own_agent_with_audit(env):
    response = env.client(env.actors["wsa-1"]).patch(
        "/api/agents/a1?operation_id=update-one",
        json={"name": "Renamed One", "capabilities": ["tool.new"],
              "promotion_episode_floor": 3})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["name"] == "Renamed One"
    assert data["capabilities"] == ["tool.new"]
    assert data["promotion_episode_floor"] == 3
    assert data["verification"]["status"] == "verified"
    assert data["operation_id"] == "agent:update:update-one"

    row = _agent(env, "a1")
    assert row.name == "Renamed One"
    assert row.capabilities == ["tool.new"]
    audits = _audits(env, "agent:update:update-one")
    assert len(audits) == 1
    audit = audits[0]
    assert audit.action == "agent_updated"
    assert audit.user_id == "wsa-1"
    assert audit.tenant_id == "t1"
    assert audit.workspace_id is None
    metadata = json.loads(audit.metadata_json)
    assert metadata["target_id"] == "a1"
    assert metadata["target_tenant_id"] == "t1"
    assert metadata["target_workspace_id"] == "ws1"
    assert metadata["prior_status"] == "student"
    assert "tool.new" not in audit.metadata_json


def test_cross_tenant_and_cross_workspace_targets_are_not_found(env):
    wsa = env.client(env.actors["wsa-1"])
    assert wsa.patch(
        "/api/agents/a2", json={"name": "Cross WS"}).status_code == 404
    assert wsa.patch(
        "/api/agents/a3", json={"name": "Cross Tenant"}).status_code == 404
    assert wsa.post("/api/agents/a2/promote").status_code == 404
    assert wsa.post("/api/agents/a3/promote").status_code == 404

    admin = env.client(env.actors["admin-1"])
    assert admin.patch(
        "/api/agents/a2", json={"name": "Cross WS Admin"}).status_code == 200
    assert admin.patch(
        "/api/agents/a3", json={"name": "Cross Tenant Admin"}).status_code == 404

    other = env.client(env.actors["admin-2"])
    assert other.patch(
        "/api/agents/a3", json={"name": "Own Tenant"}).status_code == 200
    assert other.patch(
        "/api/agents/a1", json={"name": "Foreign"}).status_code == 404


@pytest.mark.parametrize("actor_id", ["member-1", "lead-1"])
def test_non_manager_roles_cannot_update_or_promote(env, actor_id):
    client = env.client(env.actors[actor_id])
    assert client.patch(
        "/api/agents/a1", json={"name": "Denied"}).status_code == 403
    assert client.post("/api/agents/a1/promote").status_code == 403
    assert _agent(env, "a1").name == "Agent One"


def test_empty_and_matching_updates_are_no_change(env):
    client = env.client(env.actors["wsa-1"])
    empty = client.patch("/api/agents/a1", json={})
    assert empty.status_code == 200, empty.text
    assert empty.json()["data"]["verification"]["status"] == "no_change"
    assert empty.json()["data"]["verification"]["effect"] == "none"
    matching = client.patch(
        "/api/agents/a1", json={"name": "Agent One"})
    assert matching.status_code == 200, matching.text
    assert matching.json()["data"]["verification"]["status"] == "no_change"
    assert _audits(env) == []


def test_stale_peer_edit_before_update_claim_refuses(env, monkeypatch):
    original = service._load_agent
    changed = {"done": False}

    def load_then_change(db, agent_id):
        row = original(db, agent_id)
        if not changed["done"] and agent_id == "a1":
            changed["done"] = True
            _peer_update(env, "a1", name="Peer Name")
        return row

    monkeypatch.setattr(service, "_load_agent", load_then_change)
    response = env.client(env.actors["wsa-1"]).patch(
        "/api/agents/a1?operation_id=stale-update",
        json={"name": "Loser"})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "STALE_TARGET"
    assert _agent(env, "a1").name == "Peer Name"
    assert _audits(env) == []


def test_update_replay_changed_material_and_later_revision(env):
    client = env.client(env.actors["wsa-1"])
    first = client.patch(
        "/api/agents/a1?operation_id=replay-update",
        json={"name": "Replay Name"})
    assert first.status_code == 200, first.text
    replay = client.patch(
        "/api/agents/a1?operation_id=replay-update",
        json={"name": "Replay Name"})
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["verification"]["status"] == "already_applied"
    assert len(_audits(env)) == 1

    changed = client.patch(
        "/api/agents/a1?operation_id=replay-update",
        json={"name": "Different Name"})
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"]["error"]["code"] == "OPERATION_CONFLICT"

    _peer_update(env, "a1", name="Later Name")
    later = client.patch(
        "/api/agents/a1?operation_id=replay-update",
        json={"name": "Replay Name"})
    assert later.status_code == 503, later.text
    assert later.json()["detail"]["error"]["code"] == "AGENT_COMMITTED_UNVERIFIED"


def test_promote_transitions_replay_and_stale(env, monkeypatch):
    client = env.client(env.actors["wsa-1"])
    first = client.post("/api/agents/a1/promote?operation_id=promote-one")
    assert first.status_code == 200, first.text
    assert first.json()["data"]["agent_status"] == "autonomous"
    assert _agent(env, "a1").status == "autonomous"
    replay = client.post("/api/agents/a1/promote?operation_id=promote-one")
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["verification"]["status"] == "already_applied"
    nochange = client.post("/api/agents/a1/promote?operation_id=promote-two")
    assert nochange.status_code == 200, nochange.text
    assert nochange.json()["data"]["verification"]["status"] == "no_change"
    assert nochange.json()["data"]["verification"]["effect"] == "none"

    original = service._load_agent
    changed = {"done": False}

    def load_then_change(db, agent_id):
        row = original(db, agent_id)
        if not changed["done"] and agent_id == "a2":
            changed["done"] = True
            _peer_update(env, "a2", status="graduated")
        return row

    monkeypatch.setattr(service, "_load_agent", load_then_change)
    stale = env.client(env.actors["admin-1"]).post(
        "/api/agents/a2/promote?operation_id=stale-promote")
    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"]["error"]["code"] == "STALE_TARGET"
    assert _agent(env, "a2").status == "graduated"


@pytest.mark.parametrize("kind", ["update", "promote"])
@pytest.mark.parametrize("change", ["deactivate", "tenant_move"])
def test_authority_change_before_claim_refuses(env, monkeypatch, kind, change):
    original = service._load_agent
    changed = {"done": False}

    def load_then_change(db, agent_id):
        row = original(db, agent_id)
        if not changed["done"] and agent_id == "a1":
            changed["done"] = True
            peer = env.Session()
            try:
                values = (
                    {"status": "inactive", "is_active": False}
                    if change == "deactivate"
                    else {"tenant_id": "t2", "workspace_id": "ws3"})
                peer.execute(update(User).where(
                    User.id == "wsa-1").values(**values))
                peer.commit()
            finally:
                peer.close()
        return row

    monkeypatch.setattr(service, "_load_agent", load_then_change)
    client = env.client(env.actors["wsa-1"])
    if kind == "update":
        response = client.patch(
            "/api/agents/a1?operation_id=authority",
            json={"name": "Nope"})
    else:
        response = client.post(
            "/api/agents/a1/promote?operation_id=authority")
    assert response.status_code in (401, 403, 409), response.text
    assert response.json()["detail"]["verification"]["effect"] == "none"
    row = _agent(env, "a1")
    assert row.name == "Agent One" and row.status == "student"
    assert _audits(env) == []


@pytest.mark.parametrize("kind", ["update", "promote"])
def test_confirmed_audit_rollback_reports_effect_none(env, monkeypatch, kind):
    original = service._audit_row

    def invalid_audit(**kwargs):
        row = original(**kwargs)
        row.action = None
        return row

    monkeypatch.setattr(service, "_audit_row", invalid_audit)
    client = env.client(env.actors["wsa-1"])
    if kind == "update":
        response = client.patch(
            "/api/agents/a1?operation_id=rollback-update",
            json={"name": "Rollback Name"})
    else:
        response = client.post(
            "/api/agents/a1/promote?operation_id=rollback-promote")
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "AGENT_TRANSACTION_ROLLED_BACK"
    assert detail["verification"]["effect"] == "none"
    assert _agent(env, "a1").name == "Agent One"
    assert _agent(env, "a1").status == "student"
    assert _audits(env) == []


def test_post_commit_readback_is_committed_unverified(env, monkeypatch):
    def unavailable(_db, expected):
        return {
            "status": "unavailable",
            "audit_id": expected["operation_id"],
        }

    monkeypatch.setattr(service, "_verify_audit", unavailable)
    response = env.client(env.actors["wsa-1"]).patch(
        "/api/agents/a1?operation_id=readback",
        json={"name": "Readback Name"})
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "AGENT_COMMITTED_UNVERIFIED"
    assert detail["verification"]["effect"] == "committed"
    assert _agent(env, "a1").name == "Readback Name"
    assert len(_audits(env, "agent:update:readback")) == 1


def test_lost_confirmation_is_effect_unknown_with_identity(env, caplog):
    db = env.Session()
    try:
        def lost_commit():
            raise RuntimeError("lost confirmation SYNTHETIC-AGENT-SECRET")

        db.commit = lost_commit
        result = service.update_agent(
            db, actor=env.actors["wsa-1"], agent_id="a1",
            changes={"name": "Lost Name"},
            operation_id="lost-confirmation")
    finally:
        db.rollback()
        db.close()

    assert result["status"] == "effect_unknown"
    assert result["verification"]["effect"] == "unknown"
    assert result["verification"]["replay"] == "do_not_repeat"
    assert result["operation_id"] == "agent:update:lost-confirmation"
    assert "SYNTHETIC-AGENT-SECRET" not in json.dumps(result)
    assert "SYNTHETIC-AGENT-SECRET" not in caplog.text
    assert _agent(env, "a1").name == "Agent One"
    assert _audits(env) == []


@pytest.mark.parametrize("field", [
    "action",
    "user_id",
    "tenant_id",
    "workspace_id",
    "success",
    "security_level",
    "resource",
    "metadata_target_id",
    "metadata_target_tenant_id",
    "metadata_target_workspace_id",
    "metadata_actor_id",
    "metadata_prior_status",
    "metadata_result_status",
    "metadata_request_digest",
    "metadata_prior_digest",
    "metadata_result_digest",
])
def test_wrong_audit_receipt_is_never_verified(env, monkeypatch, field):
    original = service._audit_row

    def wrong_audit(**kwargs):
        row = original(**kwargs)
        metadata = json.loads(row.metadata_json or "{}")
        if field == "action":
            row.action = "wrong-action"
        elif field == "user_id":
            row.user_id = "member-1"
        elif field == "tenant_id":
            row.tenant_id = "t2"
        elif field == "workspace_id":
            row.workspace_id = "workspace-x"
        elif field == "success":
            row.success = False
        elif field == "security_level":
            row.security_level = "low"
        elif field == "resource":
            row.resource = "agent:other"
        elif field == "metadata_target_id":
            metadata["target_id"] = "other"
        elif field == "metadata_target_tenant_id":
            metadata["target_tenant_id"] = "t2"
        elif field == "metadata_target_workspace_id":
            metadata["target_workspace_id"] = "ws2"
        elif field == "metadata_actor_id":
            metadata["actor_id"] = "member-1"
        elif field == "metadata_prior_status":
            metadata["prior_status"] = "intern"
        elif field == "metadata_result_status":
            metadata["result_status"] = "intern"
        elif field == "metadata_request_digest":
            metadata["request_digest"] = "wrong-request"
        elif field == "metadata_prior_digest":
            metadata["prior_digest"] = "wrong-prior"
        elif field == "metadata_result_digest":
            metadata["result_digest"] = "wrong-result"
        row.metadata_json = json.dumps(metadata)
        return row

    monkeypatch.setattr(service, "_audit_row", wrong_audit)
    response = env.client(env.actors["wsa-1"]).patch(
        f"/api/agents/a1?operation_id=audit-{field}",
        json={"name": f"Audit {field}"})
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "AGENT_COMMITTED_UNVERIFIED"
    assert detail["verification"]["status"] in ("refuted", "unavailable")
    assert detail["verification"]["effect"] == "committed"


def test_raw_capabilities_are_absent_from_audit_and_logs(env, caplog):
    response = env.client(env.actors["wsa-1"]).patch(
        "/api/agents/a1?operation_id=cap-secret",
        json={"capabilities": ["SECRET_CAPABILITY"]})
    assert response.status_code == 200, response.text
    audit = _audits(env, "agent:update:cap-secret")[0]
    assert "SECRET_CAPABILITY" not in (audit.metadata_json or "")
    assert "SECRET_CAPABILITY" not in (audit.description or "")
    assert "SECRET_CAPABILITY" not in caplog.text


def test_anonymous_requests_are_refused(env):
    env.app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(env.app, raise_server_exceptions=False)
    assert client.patch(
        "/api/agents/a1", json={"name": "Anon"}).status_code == 401
    assert client.post("/api/agents/a1/promote").status_code == 401
    assert _agent(env, "a1").name == "Agent One"
