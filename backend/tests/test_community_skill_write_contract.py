"""Failure-first contracts for verified community-skill promote/delete."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

import core.community_skill_write_service as service
from api.skill_routes import router as skill_router
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import AuditLog, SkillExecution, Tenant, User


def _skill(
    skill_id: str, *, status: str = "Untrusted",
    name: str = "Test Skill", body: str = "body",
    scan: dict | None = None, source: str = "community",
) -> SkillExecution:
    return SkillExecution(
        id=skill_id,
        agent_id="system",
        skill_id=f"community_{name}_{skill_id[:8]}",
        tenant_id="system",
        workspace_id="default",
        status=status,
        input_params={
            "skill_name": name,
            "skill_type": "prompt_only",
            "skill_body": body,
            "packages": [],
        },
        skill_source=source,
        security_scan_result=scan or {"risk_level": "MEDIUM"},
        sandbox_enabled=False,
    )


@pytest.fixture()
def env(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/community-skill.db",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    seed = Session()
    seed.add_all([
        Tenant(id="system", name="System", subdomain="system"),
        Tenant(id="default", name="Personal", subdomain="personal"),
    ])
    users = {
        "member": User(
            id="user-member", tenant_id="default", email="member@example.com",
            first_name="Mem", last_name="Ber", role="member",
            status="active", is_active=True),
        "lead": User(
            id="user-lead", tenant_id="default", email="lead@example.com",
            first_name="Team", last_name="Lead", role="team_lead",
            status="active", is_active=True),
        "other_lead": User(
            id="user-other-lead", tenant_id="system",
            email="other@example.com", first_name="Other", last_name="Lead",
            role="team_lead", status="active", is_active=True),
    }
    seed.add_all(users.values())
    seed.commit()
    seed.close()

    def db_override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    def make_app(user=None):
        app = FastAPI()
        app.include_router(skill_router)
        app.dependency_overrides[get_db] = db_override
        if user is not None:
            app.dependency_overrides[get_current_user] = lambda: user
        return app

    app = make_app()

    def client(user: User):
        return TestClient(make_app(user), raise_server_exceptions=False)

    actors = {
        key: Session().query(User).filter(User.id == user.id).one()
        for key, user in users.items()
    }
    yield SimpleNamespace(
        engine=engine, Session=Session, app=app, client=client,
        actors=actors,
    )


def _rows(env):
    db = env.Session()
    try:
        return db.query(SkillExecution).all()
    finally:
        db.close()


def _audits(env):
    db = env.Session()
    try:
        return db.query(AuditLog).all()
    finally:
        db.close()


def _op(suffix, action="promote"):
    return f"community-skill:{action}:{suffix}"


def _peer_update(env, skill_id, **values):
    db = env.Session()
    try:
        db.execute(update(SkillExecution).where(
            SkillExecution.id == skill_id).values(**values))
        db.commit()
    finally:
        db.close()


def test_authority_and_promote_roundtrip(env):
    member = env.client(env.actors["member"])
    denied = member.post("/api/skills/promote", json={"skill_id": "s1"})
    assert denied.status_code == 403, denied.text

    db = env.Session()
    db.add_all([
        _skill("s1", name="Greeter"),
        _skill("s1-other", name="OtherTenant"),
    ])
    db.commit()
    db.close()

    lead = env.client(env.actors["lead"])
    promoted = lead.post(
        "/api/skills/promote?operation_id=promote-one",
        json={"skill_id": "s1"})
    assert promoted.status_code == 200, promoted.text
    body = promoted.json()
    assert body["data"]["status"] == "Active"
    assert body["data"]["previous_status"] == "Untrusted"
    assert body["data"]["verification"]["status"] == "verified"

    db = env.Session()
    row = db.query(SkillExecution).filter(SkillExecution.id == "s1").one()
    assert row.status == "Active"
    audit = db.query(AuditLog).filter(
        AuditLog.id == _op("promote-one")).one()
    assert audit.action == "community_skill_promoted"
    assert audit.tenant_id is None and audit.workspace_id is None
    metadata = json.loads(audit.metadata_json)
    assert metadata["scope_json"] == json.dumps(
        {"registry": "community", "tenant_id": "system",
         "workspace_id": "default"},
        sort_keys=True, separators=(",", ":"))
    db.close()

    # The community registry is platform-global: a team lead from another
    # tenant may review it, but still only through the verified route.
    other = env.client(env.actors["other_lead"]).post(
        "/api/skills/promote?operation_id=promote-other",
        json={"skill_id": "s1-other"})
    assert other.status_code == 200, other.text
    assert other.json()["data"]["status"] == "Active"


def test_promote_replay_changed_material_and_later_revision(env):
    db = env.Session()
    db.add_all([
        _skill("s2", name="Replay"),
        _skill("s2-other", name="Other"),
    ])
    db.commit()
    db.close()
    lead = env.client(env.actors["lead"])
    first = lead.post(
        "/api/skills/promote?operation_id=replay-one",
        json={"skill_id": "s2"})
    assert first.status_code == 200, first.text
    replay = lead.post(
        "/api/skills/promote?operation_id=replay-one",
        json={"skill_id": "s2"})
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["verification"]["status"] == (
        "already_applied")
    assert len(_audits(env)) == 1

    changed = lead.post(
        "/api/skills/promote?operation_id=replay-one",
        json={"skill_id": "s2-other"})
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"]["error"]["code"] == "OPERATION_CONFLICT"

    _peer_update(env, "s2", input_params={
        "skill_name": "Replay", "skill_type": "prompt_only",
        "skill_body": "later", "packages": [],
    })
    later = lead.post(
        "/api/skills/promote?operation_id=replay-one",
        json={"skill_id": "s2"})
    assert later.status_code == 503, later.text
    assert later.json()["detail"]["error"]["code"] == (
        "COMMUNITY_SKILL_COMMITTED_UNVERIFIED")


def test_promote_stale_writer_refuses_without_overwrite(env, monkeypatch):
    db = env.Session()
    db.add(_skill("s3", name="Stale"))
    db.commit()
    db.close()
    original = service._read_skill
    state = {"changed": False}

    def read_then_peer(db, skill_id):
        row = original(db, skill_id)
        if row is not None and not state["changed"]:
            state["changed"] = True
            _peer_update(env, skill_id, status="Untrusted",
                         input_params={
                             "skill_name": "Peer",
                             "skill_type": "prompt_only",
                             "skill_body": "peer",
                             "packages": [],
                         })
        return row

    monkeypatch.setattr(service, "_read_skill", read_then_peer)
    response = env.client(env.actors["lead"]).post(
        "/api/skills/promote", json={"skill_id": "s3"})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == (
        "STALE_COMMUNITY_SKILL")
    assert _rows(env)[0].input_params["skill_name"] == "Peer"


def test_delete_requires_team_lead_and_authorized_owner_succeeds(env):
    """Unauthorized member 403 twin plus the authorized team-lead positive."""
    db = env.Session()
    db.add(_skill("d-auth", name="AuthDelete"))
    db.commit()
    db.close()

    member = env.client(env.actors["member"])
    denied = member.delete("/api/skills/d-auth")
    assert denied.status_code == 403, denied.text
    assert _rows(env)[0].id == "d-auth"

    lead = env.client(env.actors["lead"])
    deleted = lead.delete("/api/skills/d-auth")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["data"]["deleted"] is True
    assert _rows(env) == []


def test_delete_replay_missing_stale_and_cloud_scope(env, monkeypatch):
    db = env.Session()
    db.add_all([
        _skill("d1", name="Delete"),
        _skill("c1", name="Cloud", source="cloud"),
    ])
    db.commit()
    db.close()
    lead = env.client(env.actors["lead"])
    deleted = lead.delete("/api/skills/d1?operation_id=delete-one")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["data"]["deleted"] is True
    replay = lead.delete("/api/skills/d1?operation_id=delete-one")
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["verification"]["status"] == (
        "already_applied")
    assert lead.delete("/api/skills/missing").status_code == 404
    assert lead.delete("/api/skills/c1").status_code == 404

    db = env.Session()
    db.add(_skill("d2", name="StaleDelete"))
    db.commit()
    db.close()
    original = service._read_skill
    state = {"changed": False}

    def read_then_peer(db, skill_id):
        row = original(db, skill_id)
        if row is not None and not state["changed"]:
            state["changed"] = True
            _peer_update(env, skill_id, input_params={
                "skill_name": "PeerDelete",
                "skill_type": "prompt_only",
                "skill_body": "peer",
                "packages": [],
            })
        return row

    monkeypatch.setattr(service, "_read_skill", read_then_peer)
    stale = lead.delete("/api/skills/d2")
    assert stale.status_code == 409, stale.text
    peer = [row for row in _rows(env) if row.id == "d2"][0]
    assert peer.input_params["skill_name"] == "PeerDelete"


def test_already_active_is_noop_without_audit(env):
    db = env.Session()
    db.add(_skill("a1", status="Active", name="Active"))
    db.commit()
    db.close()
    response = env.client(env.actors["lead"]).post(
        "/api/skills/promote", json={"skill_id": "a1"})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["verification"]["status"] == (
        "already_applied")
    assert response.json()["data"]["verification"]["effect"] == "none"
    assert _audits(env) == []


@pytest.mark.parametrize("kind", ["promote", "delete"])
def test_audit_rollback_reports_effect_none(env, monkeypatch, kind):
    db = env.Session()
    db.add(_skill("r1", name="Rollback"))
    db.commit()
    db.close()
    original = service._audit_row

    def invalid_audit(**kwargs):
        row = original(**kwargs)
        row.action = None
        return row

    monkeypatch.setattr(service, "_audit_row", invalid_audit)
    lead = env.client(env.actors["lead"])
    if kind == "promote":
        response = lead.post(
            "/api/skills/promote?operation_id=rollback-promote",
            json={"skill_id": "r1"})
    else:
        response = lead.delete(
            "/api/skills/r1?operation_id=rollback-delete")
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == (
        "COMMUNITY_SKILL_TRANSACTION_ROLLED_BACK")
    assert detail["verification"]["effect"] == "none"
    row = _rows(env)[0]
    assert row.status == "Untrusted"
    assert _audits(env) == []


def test_post_commit_readback_is_committed_unverified(env, monkeypatch):
    db = env.Session()
    db.add(_skill("u1", name="Readback"))
    db.commit()
    db.close()

    def unavailable(_db, expected):
        return {"status": "unavailable",
                "audit_id": expected["operation_id"]}

    monkeypatch.setattr(service, "_verify_audit", unavailable)
    response = env.client(env.actors["lead"]).post(
        "/api/skills/promote?operation_id=readback",
        json={"skill_id": "u1"})
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == (
        "COMMUNITY_SKILL_COMMITTED_UNVERIFIED")
    assert detail["verification"]["effect"] == "committed"
    assert detail["operation_id"] == _op("readback")


def test_lost_confirmation_is_effect_unknown(env, caplog):
    db = env.Session()
    db.add(_skill("l1", name="Lost"))
    db.commit()
    db.close()
    db = env.Session()

    def lost_commit():
        raise RuntimeError("lost confirmation SYNTHETIC-SKILL-SECRET")

    db.commit = lost_commit
    try:
        result = service.promote_skill(
            db, actor=env.actors["lead"], skill_id="l1",
            operation_id="lost")
    finally:
        db.rollback()
        db.close()
    assert result["status"] == "effect_unknown"
    assert result["verification"]["effect"] == "unknown"
    assert result["verification"]["replay"] == "do_not_repeat"
    assert "SYNTHETIC-SKILL-SECRET" not in json.dumps(result)
    assert "SYNTHETIC-SKILL-SECRET" not in caplog.text


@pytest.mark.parametrize("field", [
    "action", "user_id", "tenant_id", "workspace_id", "success",
    "security_level", "metadata_scope_json", "metadata_target_digest",
    "metadata_material_digest", "metadata_result_digest",
])
def test_wrong_audit_receipt_is_never_verified(env, monkeypatch, field):
    db = env.Session()
    db.add(_skill("t1", name="Tamper"))
    db.commit()
    db.close()
    original = service._audit_row

    def wrong_audit(**kwargs):
        row = original(**kwargs)
        metadata = json.loads(row.metadata_json or "{}")
        if field == "action":
            row.action = "wrong-action"
        elif field == "user_id":
            row.user_id = "user-other"
        elif field == "tenant_id":
            row.tenant_id = "default"
        elif field == "workspace_id":
            row.workspace_id = "workspace-x"
        elif field == "success":
            row.success = False
        elif field == "security_level":
            row.security_level = "low"
        elif field == "metadata_scope_json":
            metadata["scope_json"] = "wrong-scope"
        elif field == "metadata_target_digest":
            metadata["target_digest"] = "wrong-target"
        elif field == "metadata_material_digest":
            metadata["material_digest"] = "wrong-material"
        elif field == "metadata_result_digest":
            metadata["result_digest"] = "wrong-result"
        row.metadata_json = json.dumps(metadata)
        return row

    monkeypatch.setattr(service, "_audit_row", wrong_audit)
    response = env.client(env.actors["lead"]).post(
        f"/api/skills/promote?operation_id=tamper-{field}",
        json={"skill_id": "t1"})
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == (
        "COMMUNITY_SKILL_COMMITTED_UNVERIFIED")
    assert detail["verification"]["status"] in ("refuted", "unavailable")


def test_raw_skill_material_is_absent_from_audit_and_logs(env, caplog):
    secret_body = "SECRET_SKILL_BODY_123"
    secret_package = "SECRET_PACKAGE_456"
    db = env.Session()
    row = _skill("x1", name="SecretSkill", body=secret_body)
    row.input_params["packages"] = [secret_package]
    db.add(row)
    db.commit()
    db.close()
    response = env.client(env.actors["lead"]).post(
        "/api/skills/promote?operation_id=secret-skill",
        json={"skill_id": "x1"})
    assert response.status_code == 200, response.text
    audit = _audits(env)[0]
    blob = (audit.metadata_json or "") + (audit.description or "")
    assert secret_body not in blob
    assert secret_package not in blob
    assert "SecretSkill" not in blob
    assert secret_body not in caplog.text
    assert secret_package not in caplog.text


def test_anonymous_requests_are_refused(env):
    client = TestClient(env.app, raise_server_exceptions=False)
    assert client.post(
        "/api/skills/promote", json={"skill_id": "s1"}).status_code == 401
    assert client.delete("/api/skills/s1").status_code == 401
