"""Credential-material and result-state repairs for the seven admin routes.

These are the narrow regressions for the independent review: the stored
credential must be verified against the authorized password, replay must bind
the exact stored credential commitment, and a confirmed atomic rollback must
report effect=none rather than a committed outcome.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import update

import core.admin_write_service as service
import core.auth as auth
from core.models import AdminRole, AdminUser, AuditLog, TenantSetting
from tests.test_admin_write_contract import (
    _client,
    _seed_budget,
    env,
)

REQUEST = {
    "email": "verifier-created@example.com",
    "name": "Verifier Created",
    "password": "Synthetic-request-password-1",
    "role_id": "role-1",
}


def _user(env, email=REQUEST["email"]):
    db = env.Session()
    try:
        return db.query(AdminUser).filter(AdminUser.email == email).first()
    finally:
        db.close()


def _count_users(env, email=REQUEST["email"]):
    db = env.Session()
    try:
        return db.query(AdminUser).filter(AdminUser.email == email).count()
    finally:
        db.close()


def _count_audit_like(env, fragment):
    db = env.Session()
    try:
        return db.query(AuditLog).filter(
            AuditLog.id.like(f"%{fragment}%")).count()
    finally:
        db.close()


def test_wrong_stored_password_cannot_certify(env, monkeypatch):
    wrong_hash = auth.get_password_hash("Synthetic-other-password-2")
    monkeypatch.setattr(
        auth, "get_password_hash", lambda password: wrong_hash)
    response = _client(env).post(
        "/api/admin/users?operation_id=wrong-password", json=REQUEST)
    assert response.status_code >= 400, response.text
    assert _count_users(env) == 0


def test_valid_credential_and_replay_twin(env):
    client = _client(env)
    first = client.post(
        "/api/admin/users?operation_id=valid-credential", json=REQUEST)
    assert first.status_code == 201, first.text
    target_id = first.json()["id"]
    db = env.Session()
    try:
        row = db.query(AdminUser).filter(AdminUser.id == target_id).one()
        assert auth.verify_password(REQUEST["password"], row.password_hash)
        assert db.query(AuditLog).filter(
            AuditLog.id == "admin:user-create:valid-credential").count() == 1
    finally:
        db.close()

    replay = client.post(
        "/api/admin/users?operation_id=valid-credential", json=REQUEST)
    assert replay.status_code == 201, replay.text
    assert replay.json()["verification"]["status"] == "already_applied"
    assert _count_users(env) == 1
    assert _count_audit_like(env, "valid-credential") == 1


def test_changed_credential_replay_refutes_without_overwrite(env):
    client = _client(env)
    first = client.post(
        "/api/admin/users?operation_id=changed-credential", json=REQUEST)
    assert first.status_code == 201, first.text
    target_id = first.json()["id"]
    reset_hash = auth.get_password_hash("Synthetic-reset-password-3")
    db = env.Session()
    try:
        db.execute(update(AdminUser).where(
            AdminUser.id == target_id).values(password_hash=reset_hash))
        db.commit()
    finally:
        db.close()

    replay = client.post(
        "/api/admin/users?operation_id=changed-credential", json=REQUEST)
    assert replay.status_code == 503, replay.text
    detail = replay.json()["detail"]
    assert detail["verification"]["status"] in ("refuted", "unavailable")
    assert _count_users(env) == 1
    db = env.Session()
    try:
        row = db.query(AdminUser).filter(AdminUser.id == target_id).one()
        assert row.password_hash == reset_hash
        assert auth.verify_password("Synthetic-reset-password-3",
                                    row.password_hash)
    finally:
        db.close()


def test_malformed_credential_replay_refutes_without_overwrite(env):
    client = _client(env)
    first = client.post(
        "/api/admin/users?operation_id=malformed-credential", json=REQUEST)
    assert first.status_code == 201, first.text
    target_id = first.json()["id"]
    db = env.Session()
    try:
        db.execute(update(AdminUser).where(
            AdminUser.id == target_id).values(
                password_hash="not-a-valid-password-hash"))
        db.commit()
    finally:
        db.close()

    replay = client.post(
        "/api/admin/users?operation_id=malformed-credential", json=REQUEST)
    assert replay.status_code == 503, replay.text
    db = env.Session()
    try:
        row = db.query(AdminUser).filter(AdminUser.id == target_id).one()
        assert row.password_hash == "not-a-valid-password-hash"
    finally:
        db.close()
    assert _count_users(env) == 1


def test_deleted_credential_replay_refutes_without_recreate(env):
    client = _client(env)
    first = client.post(
        "/api/admin/users?operation_id=deleted-credential", json=REQUEST)
    assert first.status_code == 201, first.text
    target_id = first.json()["id"]
    db = env.Session()
    try:
        db.query(AdminUser).filter(AdminUser.id == target_id).delete()
        db.commit()
    finally:
        db.close()

    replay = client.post(
        "/api/admin/users?operation_id=deleted-credential", json=REQUEST)
    assert replay.status_code == 503, replay.text
    assert _count_users(env) == 0


@pytest.mark.parametrize("kind", ["role", "user", "budget"])
def test_confirmed_audit_rollback_reports_effect_none(
        env, monkeypatch, kind):
    original = service._audit_row

    def invalid_audit(**kwargs):
        row = original(**kwargs)
        row.action = None
        return row

    monkeypatch.setattr(service, "_audit_row", invalid_audit)
    client = _client(env)
    if kind == "role":
        name = "Must Roll Back Role"
        response = client.post(
            "/api/admin/roles?operation_id=rollback-role",
            json={"name": name, "permissions": {"users": True}})
        db = env.Session()
        try:
            assert db.query(AdminRole).filter(
                AdminRole.name == name).count() == 0
        finally:
            db.close()
    elif kind == "user":
        email = "rollback-user@example.com"
        response = client.post(
            "/api/admin/users?operation_id=rollback-user",
            json={"email": email, "name": "Rollback User",
                  "password": "password123", "role_id": "role-1"})
        db = env.Session()
        try:
            assert db.query(AdminUser).filter(
                AdminUser.email == email).count() == 0
        finally:
            db.close()
    else:
        _seed_budget(env, json.dumps({"budget_limit_usd": 10.0}))
        response = client.put(
            "/api/admin/tenants/tenant-1/budget?operation_id=rollback-budget",
            json={"budget_limit_usd": 25.0})
        db = env.Session()
        try:
            row = db.query(TenantSetting).filter(
                TenantSetting.tenant_id == "tenant-1",
                TenantSetting.setting_key == "billing").one()
            assert json.loads(row.setting_value)["budget_limit_usd"] == 10.0
        finally:
            db.close()

    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["verification"]["effect"] == "none", detail
    assert detail["error"]["code"] == "ADMIN_TRANSACTION_ROLLED_BACK"
    assert _count_audit_like(env, f"rollback-{kind}") == 0


def test_post_commit_readback_failure_remains_committed_unverified(
        env, monkeypatch):
    def unavailable(_db, expected):
        return {
            "status": "unavailable",
            "audit_id": expected["operation_id"],
        }

    monkeypatch.setattr(service, "_verify_audit", unavailable)
    response = _client(env).post(
        "/api/admin/roles?operation_id=readback-fail",
        json={"name": "Readback Fail", "permissions": {"users": True}})
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "ADMIN_COMMITTED_UNVERIFIED"
    assert detail["verification"]["effect"] == "committed"
    assert detail["operation_id"] == "admin:role-create:readback-fail"
    db = env.Session()
    try:
        assert db.query(AdminRole).filter(
            AdminRole.name == "Readback Fail").count() == 1
        assert db.query(AuditLog).filter(
            AuditLog.id == "admin:role-create:readback-fail").count() == 1
    finally:
        db.close()


def test_lost_confirmation_remains_effect_unknown_with_identity(
        env, monkeypatch, caplog):
    original_override = env.app.dependency_overrides[service.__name__] if (
        service.__name__ in env.app.dependency_overrides) else None
    from core.database import get_db

    def flaky_db():
        session = env.Session()
        state = {"failed": False}
        original_commit = session.commit

        def commit():
            if not state["failed"] and any(
                    isinstance(row, AuditLog) for row in session.new):
                state["failed"] = True
                raise RuntimeError(
                    "lost confirmation SYNTHETIC-ADMIN-SECRET")
            return original_commit()

        session.commit = commit
        try:
            yield session
        finally:
            session.close()

    env.app.dependency_overrides[get_db] = flaky_db
    try:
        response = _client(env).post(
            "/api/admin/roles?operation_id=lost-confirmation",
            json={"name": "Lost Confirmation", "permissions": {"users": True}})
    finally:
        if original_override is not None:
            env.app.dependency_overrides[get_db] = original_override
        else:
            env.app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "ADMIN_EFFECT_UNKNOWN"
    assert detail["verification"]["effect"] == "unknown"
    assert detail["operation_id"] == "admin:role-create:lost-confirmation"
    assert detail["replay"] == "do_not_repeat"
    assert "SYNTHETIC-ADMIN-SECRET" not in response.text
    assert "SYNTHETIC-ADMIN-SECRET" not in caplog.text


def test_unique_target_conflict_is_truthful(env):
    db = env.Session()
    try:
        db.add(AdminRole(
            id="existing-role", name="Existing Role",
            permissions={"users": True}, description="existing"))
        db.commit()
    finally:
        db.close()
    response = _client(env).post(
        "/api/admin/roles?operation_id=duplicate-role",
        json={"name": "Existing Role", "permissions": {"users": True}})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "CONFLICT"
    assert _count_audit_like(env, "duplicate-role") == 0
