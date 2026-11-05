"""Failure-first contracts for TEAM_LEAD+ community-skill decisions."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

import core.skill_review_write_service as service
from api.skill_routes import router as skill_router
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import AuditLog, SkillExecution, Tenant, User


@pytest.fixture()
def env(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/skill-review.db",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    seed = Session()
    tenants = [
        Tenant(id="system", name="System", subdomain="system"),
        Tenant(id="t1", name="Tenant One", subdomain="tenant-one"),
    ]
    users = [
        User(
            id="lead-1", tenant_id="t1", email="lead@example.com",
            first_name="Lead", last_name="One", role="team_lead",
            status="active", is_active=True),
        User(
            id="admin-1", tenant_id="t1", email="admin@example.com",
            first_name="Admin", last_name="One", role="admin",
            status="active", is_active=True),
        User(
            id="member-1", tenant_id="t1", email="member@example.com",
            first_name="Member", last_name="One", role="member",
            status="active", is_active=True),
        User(
            id="viewer-1", tenant_id="t1", email="viewer@example.com",
            first_name="Viewer", last_name="One", role="viewer",
            status="active", is_active=True),
        User(
            id="guest-1", tenant_id="t1", email="guest@example.com",
            first_name="Guest", last_name="One", role="guest",
            status="active", is_active=True),
    ]
    rows = [
        SkillExecution(
            id="s-untrusted", agent_id="system",
            skill_id="community_untrusted", tenant_id="system",
            workspace_id="default", status="Untrusted",
            input_params={
                "skill_name": "Untrusted Skill",
                "skill_body": "SECRET_SKILL_BODY",
                "packages": ["SECRET_PACKAGE"],
            },
            skill_source="community",
            security_scan_result={
                "risk_level": "HIGH", "finding": "SECRET_SCAN_FINDING"},
            sandbox_enabled=False),
        SkillExecution(
            id="s-active", agent_id="system",
            skill_id="community_active", tenant_id="system",
            workspace_id="default", status="Active",
            input_params={"skill_name": "Active Skill", "skill_body": "body"},
            skill_source="community",
            security_scan_result={"risk_level": "LOW"},
            sandbox_enabled=False),
        SkillExecution(
            id="s-other", agent_id="system",
            skill_id="community_other", tenant_id="system",
            workspace_id="default", status="Untrusted",
            input_params={"skill_name": "Other Skill", "skill_body": "other"},
            skill_source="community",
            security_scan_result={"risk_level": "MEDIUM"},
            sandbox_enabled=True),
        SkillExecution(
            id="s-cloud", agent_id="system",
            skill_id="cloud_skill", tenant_id="system",
            workspace_id="default", status="Active",
            input_params={"skill_name": "Cloud Skill"},
            skill_source="cloud",
            security_scan_result={},
            sandbox_enabled=False),
    ]
    seed.add_all(tenants + users + rows)
    seed.commit()
    seed.close()

    app = FastAPI()
    app.include_router(skill_router)

    def db_override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = db_override

    def client(user: User):
        scoped = FastAPI()
        scoped.include_router(skill_router)
        scoped.dependency_overrides[get_db] = db_override
        scoped.dependency_overrides[get_current_user] = lambda: user
        return TestClient(scoped, raise_server_exceptions=False)

    actors = {
        "lead-1": Session().query(User).filter(User.id == "lead-1").one(),
        "admin-1": Session().query(User).filter(User.id == "admin-1").one(),
        "member-1": Session().query(User).filter(User.id == "member-1").one(),
        "viewer-1": Session().query(User).filter(User.id == "viewer-1").one(),
        "guest-1": Session().query(User).filter(User.id == "guest-1").one(),
    }
    yield SimpleNamespace(
        engine=engine, Session=Session, app=app, client=client,
        actors=actors,
    )


def _row(env, skill_id):
    db = env.Session()
    try:
        return db.query(SkillExecution).filter(
            SkillExecution.id == skill_id).first()
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


def _peer_update(env, skill_id, **values):
    db = env.Session()
    try:
        db.execute(update(SkillExecution).where(
            SkillExecution.id == skill_id).values(**values))
        db.commit()
    finally:
        db.close()


def test_team_lead_promote_verifies_and_audits(env):
    response = env.client(env.actors["lead-1"]).post(
        "/api/skills/promote?operation_id=promote-one",
        json={"skill_id": "s-untrusted"})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "Active"
    assert data["previous_status"] == "Untrusted"
    assert data["verification"]["status"] == "verified"
    assert data["operation_id"] == "skill:promote:promote-one"

    row = _row(env, "s-untrusted")
    assert row.status == "Active"
    audits = _audits(env, "skill:promote:promote-one")
    assert len(audits) == 1
    audit = audits[0]
    assert audit.action == "community_skill_promoted"
    assert audit.user_id == "lead-1"
    assert audit.tenant_id == "t1"
    assert audit.workspace_id is None
    assert audit.success is True
    metadata = json.loads(audit.metadata_json)
    assert metadata["target_id"] == "s-untrusted"
    assert metadata["target_tenant_id"] == "system"
    assert metadata["prior_status"] == "Untrusted"
    assert metadata["result_status"] == "Active"
    assert "SECRET_SKILL_BODY" not in audit.metadata_json
    assert "SECRET_PACKAGE" not in audit.metadata_json
    assert "SECRET_SCAN_FINDING" not in audit.metadata_json
    assert "SECRET_SKILL_BODY" not in (audit.description or "")
    assert "SECRET_SCAN_FINDING" not in (audit.description or "")


def test_admin_can_promote(env):
    response = env.client(env.actors["admin-1"]).post(
        "/api/skills/promote?operation_id=admin-promote",
        json={"skill_id": "s-untrusted"})
    assert response.status_code == 200, response.text
    assert _row(env, "s-untrusted").status == "Active"


@pytest.mark.parametrize("actor_id", ["member-1", "viewer-1", "guest-1"])
def test_non_review_roles_cannot_promote_or_delete(env, actor_id):
    client = env.client(env.actors[actor_id])
    promote = client.post(
        "/api/skills/promote?operation_id=role-promote",
        json={"skill_id": "s-untrusted"})
    assert promote.status_code == 403, promote.text
    delete = client.delete(
        "/api/skills/s-untrusted?operation_id=role-delete")
    assert delete.status_code == 403, delete.text
    assert _row(env, "s-untrusted").status == "Untrusted"
    assert _audits(env) == []


def test_anonymous_cannot_promote_or_delete(env):
    env.app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(env.app, raise_server_exceptions=False)
    assert client.post(
        "/api/skills/promote", json={"skill_id": "s-untrusted"}
    ).status_code == 401
    assert client.delete("/api/skills/s-untrusted").status_code == 401
    assert _row(env, "s-untrusted").status == "Untrusted"
    assert _audits(env) == []


def test_missing_and_cloud_targets_are_not_found(env):
    client = env.client(env.actors["lead-1"])
    assert client.post(
        "/api/skills/promote", json={"skill_id": "missing"}
    ).status_code == 404
    assert client.delete("/api/skills/missing").status_code == 404
    assert client.post(
        "/api/skills/promote", json={"skill_id": "s-cloud"}
    ).status_code == 404
    assert client.delete("/api/skills/s-cloud").status_code == 404
    assert _row(env, "s-cloud").status is not None
    assert _audits(env) == []


def test_already_active_new_operation_is_no_change(env):
    response = env.client(env.actors["lead-1"]).post(
        "/api/skills/promote?operation_id=already-active",
        json={"skill_id": "s-active"})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "Active"
    assert data["previous_status"] == "Active"
    assert data["verification"]["status"] == "no_change"
    assert data["verification"]["effect"] == "none"
    assert _row(env, "s-active").status == "Active"
    assert _audits(env) == []


def test_unsupported_status_is_refused(env):
    _peer_update(env, "s-other", status="pending")
    response = env.client(env.actors["lead-1"]).post(
        "/api/skills/promote?operation_id=unsupported",
        json={"skill_id": "s-other"})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "UNSUPPORTED_STATUS"
    assert _row(env, "s-other").status == "pending"
    assert _audits(env) == []


def test_promote_replay_changed_material_and_later_revision(env, monkeypatch):
    client = env.client(env.actors["lead-1"])
    first = client.post(
        "/api/skills/promote?operation_id=replay-promote",
        json={"skill_id": "s-untrusted"})
    assert first.status_code == 200, first.text
    replay = client.post(
        "/api/skills/promote?operation_id=replay-promote",
        json={"skill_id": "s-untrusted"})
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["verification"]["status"] == (
        "already_applied")
    assert len(_audits(env)) == 1

    _peer_update(env, "s-untrusted", status="Untrusted")
    later = client.post(
        "/api/skills/promote?operation_id=replay-promote",
        json={"skill_id": "s-untrusted"})
    assert later.status_code == 503, later.text
    assert later.json()["detail"]["error"]["code"] == (
        "SKILL_COMMITTED_UNVERIFIED")
    assert len(_audits(env)) == 1

    _peer_update(env, "s-untrusted", status="Active",
                 input_params={"skill_name": "Changed"})
    changed = client.post(
        "/api/skills/promote?operation_id=replay-promote",
        json={"skill_id": "s-untrusted"})
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"]["error"]["code"] == "OPERATION_CONFLICT"


@pytest.mark.parametrize("kind", ["promote", "delete"])
@pytest.mark.parametrize("change", ["deactivate", "tenant_move"])
def test_authority_change_before_claim_refuses(env, monkeypatch, kind, change):
    original = service._load_skill
    changed = {"done": False}

    def load_then_change(db, skill_id):
        row = original(db, skill_id)
        if not changed["done"]:
            changed["done"] = True
            peer = env.Session()
            try:
                values = (
                    {"status": "inactive", "is_active": False}
                    if change == "deactivate"
                    else {"tenant_id": "tenant-2"})
                peer.execute(update(User).where(
                    User.id == "lead-1").values(**values))
                peer.commit()
            finally:
                peer.close()
        return row

    monkeypatch.setattr(service, "_load_skill", load_then_change)
    client = env.client(env.actors["lead-1"])
    if kind == "promote":
        response = client.post(
            "/api/skills/promote?operation_id=authority-change",
            json={"skill_id": "s-untrusted"})
    else:
        response = client.delete(
            "/api/skills/s-untrusted?operation_id=authority-change")
    assert response.status_code in (401, 403, 409), response.text
    detail = response.json()["detail"]
    assert detail["verification"]["effect"] == "none"
    row = _row(env, "s-untrusted")
    assert row is not None and row.status == "Untrusted"
    assert _audits(env) == []


def test_stale_material_before_promote_claim_refuses(env, monkeypatch):
    original = service._claim_actor

    def claim_then_change(db, actor):
        peer = env.Session()
        try:
            peer.execute(update(SkillExecution).where(
                SkillExecution.id == "s-untrusted").values(
                    input_params={"skill_name": "Peer Changed"}))
            peer.commit()
        finally:
            peer.close()
        return original(db, actor)

    monkeypatch.setattr(service, "_claim_actor", claim_then_change)
    response = env.client(env.actors["lead-1"]).post(
        "/api/skills/promote?operation_id=stale-promote",
        json={"skill_id": "s-untrusted"})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "STALE_TARGET"
    assert _row(env, "s-untrusted").status == "Untrusted"
    assert _audits(env) == []


def test_delete_untrusted_active_replay_and_missing(env):
    client = env.client(env.actors["lead-1"])
    deleted = client.delete("/api/skills/s-untrusted?operation_id=del-one")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["data"]["deleted"] is True
    assert _row(env, "s-untrusted") is None
    replay = client.delete("/api/skills/s-untrusted?operation_id=del-one")
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["verification"]["status"] == "already_applied"
    assert client.delete(
        "/api/skills/s-untrusted?operation_id=del-two").status_code == 404
    assert client.delete(
        "/api/skills/s-active?operation_id=del-active").status_code == 200
    assert _row(env, "s-active") is None
    assert len(_audits(env)) == 2


def test_stale_material_before_delete_refuses(env, monkeypatch):
    original = service._claim_actor

    def claim_then_change(db, actor):
        peer = env.Session()
        try:
            peer.execute(update(SkillExecution).where(
                SkillExecution.id == "s-untrusted").values(
                    security_scan_result={"risk_level": "PEER"}))
            peer.commit()
        finally:
            peer.close()
        return original(db, actor)

    monkeypatch.setattr(service, "_claim_actor", claim_then_change)
    response = env.client(env.actors["lead-1"]).delete(
        "/api/skills/s-untrusted?operation_id=stale-delete")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "STALE_TARGET"
    assert _row(env, "s-untrusted") is not None
    assert _audits(env) == []


def test_promote_then_delete_then_promote_replay_is_unverified(env):
    client = env.client(env.actors["lead-1"])
    assert client.post(
        "/api/skills/promote?operation_id=p-then-d",
        json={"skill_id": "s-untrusted"}).status_code == 200
    assert client.delete(
        "/api/skills/s-untrusted?operation_id=delete-after-promote"
    ).status_code == 200
    replay = client.post(
        "/api/skills/promote?operation_id=p-then-d",
        json={"skill_id": "s-untrusted"})
    assert replay.status_code == 503, replay.text
    assert replay.json()["detail"]["error"]["code"] == (
        "SKILL_COMMITTED_UNVERIFIED")


@pytest.mark.parametrize("kind", ["promote", "delete"])
def test_confirmed_audit_rollback_reports_effect_none(env, monkeypatch, kind):
    original = service._audit_row

    def invalid_audit(**kwargs):
        row = original(**kwargs)
        row.action = None
        return row

    monkeypatch.setattr(service, "_audit_row", invalid_audit)
    client = env.client(env.actors["lead-1"])
    if kind == "promote":
        response = client.post(
            "/api/skills/promote?operation_id=rollback-promote",
            json={"skill_id": "s-untrusted"})
    else:
        response = client.delete(
            "/api/skills/s-other?operation_id=rollback-delete")
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "SKILL_TRANSACTION_ROLLED_BACK"
    assert detail["verification"]["effect"] == "none"
    assert detail["verification"]["status"] == "refused"
    if kind == "promote":
        assert _row(env, "s-untrusted").status == "Untrusted"
    else:
        assert _row(env, "s-other") is not None
    assert _audits(env) == []


def test_post_commit_readback_is_committed_unverified(env, monkeypatch):
    def unavailable(_db, expected):
        return {
            "status": "unavailable",
            "audit_id": expected["operation_id"],
        }

    monkeypatch.setattr(service, "_verify_audit", unavailable)
    response = env.client(env.actors["lead-1"]).post(
        "/api/skills/promote?operation_id=readback",
        json={"skill_id": "s-untrusted"})
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "SKILL_COMMITTED_UNVERIFIED"
    assert detail["verification"]["effect"] == "committed"
    assert _row(env, "s-untrusted").status == "Active"
    assert len(_audits(env, "skill:promote:readback")) == 1


def test_lost_confirmation_is_effect_unknown_with_identity(env, caplog):
    db = env.Session()
    try:
        def lost_commit():
            raise RuntimeError("lost confirmation SYNTHETIC-SKILL-SECRET")

        db.commit = lost_commit
        result = service.promote_community_skill(
            db, actor=env.actors["lead-1"], skill_id="s-untrusted",
            operation_id="lost-confirmation")
    finally:
        db.rollback()
        db.close()

    assert result["status"] == "effect_unknown"
    assert result["verification"]["effect"] == "unknown"
    assert result["verification"]["replay"] == "do_not_repeat"
    assert result["operation_id"] == "skill:promote:lost-confirmation"
    assert "SYNTHETIC-SKILL-SECRET" not in json.dumps(result)
    assert "SYNTHETIC-SKILL-SECRET" not in caplog.text
    assert _row(env, "s-untrusted").status == "Untrusted"
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
            row.tenant_id = "system"
        elif field == "workspace_id":
            row.workspace_id = "workspace-x"
        elif field == "success":
            row.success = False
        elif field == "security_level":
            row.security_level = "low"
        elif field == "resource":
            row.resource = "community_skill:other"
        elif field == "metadata_target_id":
            metadata["target_id"] = "other"
        elif field == "metadata_target_tenant_id":
            metadata["target_tenant_id"] = "other"
        elif field == "metadata_actor_id":
            metadata["actor_id"] = "member-1"
        elif field == "metadata_prior_status":
            metadata["prior_status"] = "Active"
        elif field == "metadata_result_status":
            metadata["result_status"] = "Untrusted"
        elif field == "metadata_request_digest":
            metadata["request_digest"] = "wrong-request"
        elif field == "metadata_prior_digest":
            metadata["prior_digest"] = "wrong-prior"
        elif field == "metadata_result_digest":
            metadata["result_digest"] = "wrong-result"
        row.metadata_json = json.dumps(metadata)
        return row

    monkeypatch.setattr(service, "_audit_row", wrong_audit)
    response = env.client(env.actors["lead-1"]).post(
        f"/api/skills/promote?operation_id=audit-{field}",
        json={"skill_id": "s-untrusted"})
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "SKILL_COMMITTED_UNVERIFIED"
    assert detail["verification"]["status"] in ("refuted", "unavailable")
    assert detail["verification"]["effect"] == "committed"
    assert _row(env, "s-untrusted").status == "Active"


def test_raw_skill_material_is_absent_from_audit_and_logs(env, caplog):
    response = env.client(env.actors["lead-1"]).post(
        "/api/skills/promote?operation_id=secret-promote",
        json={"skill_id": "s-untrusted"})
    assert response.status_code == 200, response.text
    audit = _audits(env, "skill:promote:secret-promote")[0]
    assert "SECRET_SKILL_BODY" not in (audit.metadata_json or "")
    assert "SECRET_PACKAGE" not in (audit.metadata_json or "")
    assert "SECRET_SCAN_FINDING" not in (audit.metadata_json or "")
    assert "SECRET_SKILL_BODY" not in (audit.description or "")
    assert "SECRET_SCAN_FINDING" not in caplog.text
