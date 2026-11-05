"""ORACLE-01 five-route auth/2FA verified-write controls.

Real scratch SQLite, real ``pyotp``, real ``AuditLog`` and real ``HITLAction``
rows. Only the rate limiter and controlled time are test seams. The service's
durable operation/backup-code/HITL state is exercised through the mounted
routes and fresh sessions.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pyotp
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from freezegun import freeze_time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.auth_2fa_routes import router as auth_2fa_router
from core.audit_service import audit_service
from core.auth import get_current_user
from core.auth_2fa_write_service import (
    disable_2fa_verified,
    enable_2fa_verified,
    setup_2fa_verified,
    verify_action_2fa_verified,
    verify_backup_code_verified,
)
from core.database import Base, get_db
from core.models import (
    AuditLog,
    AuthTwoFactorBackupCode,
    AuthTwoFactorOperation,
    HITLAction,
    User,
)

TEST_SECRET = "JBSWY3DPEHPK3PXP"
AUTH_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path}/auth-2fa-writes.db",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    @contextlib.contextmanager
    def fresh_session():
        session = Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr("core.database.SessionLocal", Session)
    monkeypatch.setattr("core.database.get_db_session", fresh_session)
    monkeypatch.setattr("core.intervention_service.get_db_session", fresh_session)
    monkeypatch.setattr("core.hitl_service.get_db_session", fresh_session)
    monkeypatch.setattr(
        "api.auth_2fa_routes._2fa_limiter.check",
        lambda request: (True, 5))
    yield SimpleNamespace(engine=engine, Session=Session, db=db)
    db.close()
    engine.dispose()


def _make_user(
    env, user_id="user-1", *, tenant="t1", workspace="ws-1",
    role="member", enabled=False, secret=None, codes=None,
    revision=0, last_step=None,
):
    user = User(
        id=user_id,
        email=f"{user_id}@example.com",
        hashed_password="x",
        first_name="T",
        last_name="U",
        role=role,
        status="active",
        tenant_id=tenant,
        workspace_id=workspace,
        two_factor_enabled=enabled,
        two_factor_secret=secret,
        two_factor_backup_codes=codes,
        two_factor_revision=revision,
        two_factor_last_totp_step=last_step,
        is_active=True,
    )
    env.db.add(user)
    env.db.commit()
    env.db.refresh(user)
    return user


def _make_action(
    env, action_id="action-1", *, tenant="t1", workspace="ws-1",
    status="pending", user_id=None, required_role=None,
    required_role_column=None,
):
    action = HITLAction(
        id=action_id,
        tenant_id=tenant,
        workspace_id=workspace,
        action_type="send_message",
        platform="internal",
        params={},
        status=status,
        priority="MEDIUM",
        user_id=user_id,
        required_role=required_role_column,
        context_snapshot=(
            {"required_role": required_role} if required_role else None),
    )
    env.db.add(action)
    env.db.commit()
    env.db.refresh(action)
    return action


def _client(env, user):
    app = FastAPI()
    app.include_router(auth_2fa_router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: env.db
    return TestClient(app, raise_server_exceptions=False)


def _refresh(env):
    env.db.expire_all()


def _codes(env, user_id):
    _refresh(env)
    return env.db.query(AuthTwoFactorBackupCode).filter(
        AuthTwoFactorBackupCode.user_id == user_id).all()


def _operations(env, user_id):
    _refresh(env)
    return env.db.query(AuthTwoFactorOperation).filter(
        AuthTwoFactorOperation.user_id == user_id).all()


def _audits(env, action=None):
    _refresh(env)
    query = env.db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    return query.all()


def test_setup_retry_preserves_pending_secret_then_refuses_after_enable(env):
    user = _make_user(env)
    client = _client(env, user)
    first = client.post("/api/auth/2fa/setup", headers=AUTH_HEADERS)
    assert first.status_code == 200, first.text
    first_body = first.json()
    secret = first_body["secret"]
    assert first_body["verification"]["status"] == "verified"
    _refresh(env)
    revision = env.db.query(User).filter(User.id == user.id).one(
    ).two_factor_revision

    second = client.post("/api/auth/2fa/setup", headers=AUTH_HEADERS)
    assert second.status_code == 200, second.text
    second_body = second.json()
    assert second_body["secret"] == secret
    assert second_body["status"] == "already_pending"
    _refresh(env)
    assert env.db.query(User).filter(User.id == user.id).one(
    ).two_factor_revision == revision

    with freeze_time("2026-01-01 00:00:00"):
        code = pyotp.TOTP(secret).now()
        enabled = client.post(
            "/api/auth/2fa/enable", json={"code": code},
            headers=AUTH_HEADERS)
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["verification"]["status"] == "verified"

    replay = client.post("/api/auth/2fa/setup", headers=AUTH_HEADERS)
    assert replay.status_code == 409, replay.text
    assert "secret" not in replay.json()
    _refresh(env)
    assert env.db.query(User).filter(User.id == user.id).one(
    ).two_factor_secret == secret


def test_enable_verified_persists_factor_and_replay_receipt(env):
    user = _make_user(env, secret=TEST_SECRET)
    client = _client(env, user)
    with freeze_time("2026-01-01 00:00:00"):
        code = pyotp.TOTP(TEST_SECRET).now()
        response = client.post(
            "/api/auth/2fa/enable?operation_id=op-enable-1",
            json={"code": code}, headers=AUTH_HEADERS)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["verification"]["status"] == "verified"
    assert len(body["data"]["backup_codes"]) == 5
    _refresh(env)
    row = env.db.query(User).filter(User.id == user.id).one()
    assert row.two_factor_enabled is True
    assert row.two_factor_revision == 1
    assert row.two_factor_last_totp_step == 1767225600 // 30
    assert len(_codes(env, user.id)) == 5
    assert _audits(env, "2fa_enabled")
    assert [op.id for op in _operations(env, user.id)] == ["op-enable-1"]

    retry = client.post(
        "/api/auth/2fa/enable?operation_id=op-enable-1",
        json={"code": code}, headers=AUTH_HEADERS)
    assert retry.status_code == 200, retry.text
    retry_body = retry.json()
    assert retry_body["verification"]["status"] == "already_applied"
    assert retry_body["data"]["backup_codes"] is None
    assert len(_audits(env, "2fa_enabled")) == 1

    conflict = client.post(
        "/api/auth/2fa/enable?operation_id=op-enable-1",
        json={"code": "000000"}, headers=AUTH_HEADERS)
    assert conflict.status_code == 409, conflict.text
    _refresh(env)
    assert env.db.query(User).filter(User.id == user.id).one(
    ).two_factor_enabled is True


def test_disable_verified_clears_factor_and_replay_receipt(env):
    user = _make_user(env, secret=TEST_SECRET)
    client = _client(env, user)
    with freeze_time("2026-01-01 00:00:00"):
        enable_code = pyotp.TOTP(TEST_SECRET).now()
        enabled = client.post(
            "/api/auth/2fa/enable", json={"code": enable_code},
            headers=AUTH_HEADERS)
    assert enabled.status_code == 200, enabled.text
    with freeze_time("2026-01-01 00:00:30"):
        disable_code = pyotp.TOTP(TEST_SECRET).now()
        disabled = client.post(
            "/api/auth/2fa/disable?operation_id=op-disable-1",
            json={"code": disable_code}, headers=AUTH_HEADERS)
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["verification"]["status"] == "verified"
    _refresh(env)
    row = env.db.query(User).filter(User.id == user.id).one()
    assert row.two_factor_enabled is False
    assert row.two_factor_secret is None
    assert row.two_factor_backup_codes is None
    assert row.two_factor_revision == 2
    assert _codes(env, user.id) == []
    assert _audits(env, "2fa_disabled")

    retry = client.post(
        "/api/auth/2fa/disable?operation_id=op-disable-1",
        json={"code": disable_code}, headers=AUTH_HEADERS)
    assert retry.status_code == 200, retry.text
    assert retry.json()["verification"]["status"] == "already_applied"
    assert len(_audits(env, "2fa_disabled")) == 1


def test_backup_code_single_use_and_replay(env):
    user = _make_user(env, secret=TEST_SECRET)
    client = _client(env, user)
    with freeze_time("2026-01-01 00:00:00"):
        enabled = client.post(
            "/api/auth/2fa/enable",
            json={"code": pyotp.TOTP(TEST_SECRET).now()},
            headers=AUTH_HEADERS)
    assert enabled.status_code == 200, enabled.text
    codes = enabled.json()["data"]["backup_codes"]
    first = client.post(
        "/api/auth/2fa/backup/verify?operation_id=op-backup-1",
        json={"code": codes[0]}, headers=AUTH_HEADERS)
    assert first.status_code == 200, first.text
    assert first.json()["verification"]["status"] == "verified"
    assert first.json()["data"]["remaining_codes"] == 4
    _refresh(env)
    assert len([row for row in _codes(env, user.id)
                if row.consumed_at is None]) == 4
    consumed = [row for row in _codes(env, user.id)
                if row.consumed_at is not None]
    assert len(consumed) == 1
    assert consumed[0].operation_id == "op-backup-1"
    assert len(_audits(env, "2fa_backup_code_used")) == 1

    same_op = client.post(
        "/api/auth/2fa/backup/verify?operation_id=op-backup-1",
        json={"code": codes[0]}, headers=AUTH_HEADERS)
    assert same_op.status_code == 200, same_op.text
    assert same_op.json()["verification"]["status"] == "already_applied"
    assert same_op.json()["data"]["remaining_codes"] is None
    assert len(_audits(env, "2fa_backup_code_used")) == 1

    replay = client.post(
        "/api/auth/2fa/backup/verify?operation_id=op-backup-2",
        json={"code": codes[0]}, headers=AUTH_HEADERS)
    assert replay.status_code == 409, replay.text
    _refresh(env)
    assert len([row for row in _codes(env, user.id)
                if row.consumed_at is not None]) == 1


def test_legacy_plaintext_backup_codes_are_backfilled(env):
    user = _make_user(
        env, enabled=True, secret=TEST_SECRET,
        codes=["ABCD-1234-EFGH-5678", "WXYZ-9999"])
    client = _client(env, user)
    response = client.post(
        "/api/auth/2fa/backup/verify",
        json={"code": "ABCD-1234-EFGH-5678"}, headers=AUTH_HEADERS)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["remaining_codes"] == 1
    _refresh(env)
    assert len(_codes(env, user.id)) == 2
    assert len([row for row in _codes(env, user.id)
                if row.consumed_at is not None]) == 1


def test_backup_code_concurrent_single_use(env):
    user = _make_user(
        env, enabled=True, secret=TEST_SECRET,
        codes=["ABCD-1234-EFGH-5678", "WXYZ-9999"])
    barrier = threading.Barrier(2)
    user_id = user.id

    def _consume(operation_id):
        barrier.wait()
        return verify_backup_code_verified(
            user_id=user_id,
            code="ABCD-1234-EFGH-5678",
            request=None,
            operation_id=operation_id,
            audit_logger=audit_service,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(_consume, ["op-concurrent-1", "op-concurrent-2"]))
    statuses = [result["status"] for result in results]
    assert statuses.count("verified") == 1, results
    assert statuses.count("refused") == 1, results
    _refresh(env)
    assert len([row for row in _codes(env, user.id)
                if row.consumed_at is not None]) == 1
    assert len(_audits(env, "2fa_backup_code_used")) == 1


def test_totp_replay_across_operations_is_refused(env):
    user = _make_user(env, enabled=True, secret=TEST_SECRET)
    _make_action(env, "action-1", user_id=user.id)
    _make_action(env, "action-2", user_id=user.id)
    client = _client(env, user)
    with freeze_time("2026-01-01 00:00:00"):
        code = pyotp.TOTP(TEST_SECRET).now()
        first = client.post(
            "/api/auth/2fa/verify-action/action-1?operation_id=op-action-1",
            json={"code": code}, headers=AUTH_HEADERS)
        assert first.status_code == 200, first.text
        replay = client.post(
            "/api/auth/2fa/verify-action/action-2?operation_id=op-action-2",
            json={"code": code}, headers=AUTH_HEADERS)
    assert replay.status_code == 409, replay.text
    _refresh(env)
    assert env.db.query(HITLAction).filter(
        HITLAction.id == "action-2").one().status == "pending"

    with freeze_time("2026-01-01 00:00:30"):
        next_code = pyotp.TOTP(TEST_SECRET).now()
        second = client.post(
            "/api/auth/2fa/verify-action/action-2?operation_id=op-action-3",
            json={"code": next_code}, headers=AUTH_HEADERS)
    assert second.status_code == 200, second.text
    _refresh(env)
    assert env.db.query(HITLAction).filter(
        HITLAction.id == "action-2").one().status == "approved"


def test_verify_action_persists_durable_resolver_and_receipt(env):
    user = _make_user(env, enabled=True, secret=TEST_SECRET)
    _make_action(env, "action-1", user_id=user.id)
    _make_action(env, "action-2", user_id=user.id)
    client = _client(env, user)
    with freeze_time("2026-01-01 00:00:00"):
        code = pyotp.TOTP(TEST_SECRET).now()
        response = client.post(
            "/api/auth/2fa/verify-action/action-1?operation_id=op-action-1",
            json={"code": code}, headers=AUTH_HEADERS)
    assert response.status_code == 200, response.text
    assert response.json()["data"] == {"status": "approved"}
    assert response.json()["verification"]["status"] == "verified"
    _refresh(env)
    action = env.db.query(HITLAction).filter(
        HITLAction.id == "action-1").one()
    assert action.status == "approved"
    assert action.reviewed_by == user.id
    assert action.reviewed_at is not None
    assert _audits(env, "hitl_action_verified_2fa")
    assert [op.id for op in _operations(env, user.id)] == ["op-action-1"]

    retry = client.post(
        "/api/auth/2fa/verify-action/action-1?operation_id=op-action-1",
        json={"code": code}, headers=AUTH_HEADERS)
    assert retry.status_code == 200, retry.text
    assert retry.json()["verification"]["status"] == "already_applied"
    assert len(_audits(env, "hitl_action_verified_2fa")) == 1

    different_target = client.post(
        "/api/auth/2fa/verify-action/action-2?operation_id=op-action-1",
        json={"code": code}, headers=AUTH_HEADERS)
    assert different_target.status_code == 409, different_target.text
    _refresh(env)
    assert env.db.query(HITLAction).filter(
        HITLAction.id == "action-2").one().status == "pending"


def test_verify_action_scope_and_role_refusals(env):
    user = _make_user(env, enabled=True, secret=TEST_SECRET)
    foreign = _make_action(
        env, "foreign-action", tenant="t2", workspace="ws-2")
    _make_action(env, "role-action", user_id=user.id,
                 required_role="team_lead")
    _make_action(env, "column-role-action", user_id=user.id,
                 required_role_column="team_lead")
    _make_action(env, "rejected-action", user_id=user.id, status="rejected")
    client = _client(env, user)
    with freeze_time("2026-01-01 00:00:00"):
        code = pyotp.TOTP(TEST_SECRET).now()
        foreign_resp = client.post(
            "/api/auth/2fa/verify-action/foreign-action",
            json={"code": code}, headers=AUTH_HEADERS)
        role_resp = client.post(
            "/api/auth/2fa/verify-action/role-action",
            json={"code": code}, headers=AUTH_HEADERS)
        column_role_resp = client.post(
            "/api/auth/2fa/verify-action/column-role-action",
            json={"code": code}, headers=AUTH_HEADERS)
        rejected_resp = client.post(
            "/api/auth/2fa/verify-action/rejected-action",
            json={"code": code}, headers=AUTH_HEADERS)
        missing_resp = client.post(
            "/api/auth/2fa/verify-action/missing-action",
            json={"code": code}, headers=AUTH_HEADERS)
    assert foreign_resp.status_code == 403, foreign_resp.text
    assert role_resp.status_code == 403, role_resp.text
    assert column_role_resp.status_code == 403, column_role_resp.text
    assert rejected_resp.status_code == 409, rejected_resp.text
    assert missing_resp.status_code == 404, missing_resp.text
    _refresh(env)
    assert env.db.query(HITLAction).filter(
        HITLAction.id == foreign.id).one().status == "pending"
    assert env.db.query(User).filter(
        User.id == user.id).one().two_factor_last_totp_step is None


def test_moved_action_scope_after_read_refuses_before_effect(
        env, monkeypatch):
    user = _make_user(env, enabled=True, secret=TEST_SECRET)
    _make_action(env, "action-1", user_id=user.id)
    client = _client(env, user)
    original_verify = pyotp.TOTP.verify
    moved = []

    def verify_then_move(self, code, *args, **kwargs):
        ok = original_verify(self, code, *args, **kwargs)
        if ok and not moved:
            with env.Session() as other:
                other.query(HITLAction).filter(
                    HITLAction.id == "action-1").update(
                        {"workspace_id": "ws-revoked"})
                other.commit()
            moved.append(True)
        return ok

    monkeypatch.setattr(pyotp.TOTP, "verify", verify_then_move)
    with freeze_time("2026-01-01 00:00:00"):
        response = client.post(
            "/api/auth/2fa/verify-action/action-1",
            json={"code": pyotp.TOTP(TEST_SECRET).now()},
            headers=AUTH_HEADERS)
    assert moved
    assert response.status_code == 409, response.text
    _refresh(env)
    assert env.db.query(HITLAction).filter(
        HITLAction.id == "action-1").one().status == "pending"
    assert env.db.query(User).filter(
        User.id == user.id).one().two_factor_last_totp_step is None


def test_stale_enable_writer_refuses_before_effect(env, monkeypatch):
    user = _make_user(env, secret=TEST_SECRET)
    client = _client(env, user)
    original_verify = pyotp.TOTP.verify
    moved = []

    def verify_then_bump(self, code, *args, **kwargs):
        ok = original_verify(self, code, *args, **kwargs)
        if ok and not moved:
            with env.Session() as other:
                other.query(User).filter(User.id == user.id).update(
                    {"two_factor_revision": 9})
                other.commit()
            moved.append(True)
        return ok

    monkeypatch.setattr(pyotp.TOTP, "verify", verify_then_bump)
    with freeze_time("2026-01-01 00:00:00"):
        response = client.post(
            "/api/auth/2fa/enable",
            json={"code": pyotp.TOTP(TEST_SECRET).now()},
            headers=AUTH_HEADERS)
    assert moved
    assert response.status_code == 409, response.text
    _refresh(env)
    row = env.db.query(User).filter(User.id == user.id).one()
    assert row.two_factor_enabled is False
    assert row.two_factor_revision == 9
    assert _codes(env, user.id) == []


def test_stale_disable_writer_refuses_before_effect(env, monkeypatch):
    user = _make_user(env, enabled=True, secret=TEST_SECRET)
    client = _client(env, user)
    original_verify = pyotp.TOTP.verify
    moved = []

    def verify_then_bump(self, code, *args, **kwargs):
        ok = original_verify(self, code, *args, **kwargs)
        if ok and not moved:
            with env.Session() as other:
                other.query(User).filter(User.id == user.id).update(
                    {"two_factor_revision": 9})
                other.commit()
            moved.append(True)
        return ok

    monkeypatch.setattr(pyotp.TOTP, "verify", verify_then_bump)
    with freeze_time("2026-01-01 00:00:00"):
        response = client.post(
            "/api/auth/2fa/disable",
            json={"code": pyotp.TOTP(TEST_SECRET).now()},
            headers=AUTH_HEADERS)
    assert moved
    assert response.status_code == 409, response.text
    _refresh(env)
    row = env.db.query(User).filter(User.id == user.id).one()
    assert row.two_factor_enabled is True
    assert row.two_factor_revision == 9


def test_totp_concurrent_same_code_approves_one_action(env):
    user = _make_user(env, enabled=True, secret=TEST_SECRET)
    _make_action(env, "action-1", user_id=user.id)
    _make_action(env, "action-2", user_id=user.id)
    barrier = threading.Barrier(2)
    user_id = user.id

    def _verify(action_id, operation_id, code):
        barrier.wait()
        return asyncio.run(verify_action_2fa_verified(
            user_id=user_id,
            action_id=action_id,
            code=code,
            request=None,
            operation_id=operation_id,
            audit_logger=audit_service,
        ))

    with freeze_time("2026-01-01 00:00:00"):
        code = pyotp.TOTP(TEST_SECRET).now()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(
                lambda pair: _verify(pair[0], pair[1], code),
                [("action-1", "op-concurrent-action-1"),
                 ("action-2", "op-concurrent-action-2")],
            ))
    statuses = [result["status"] for result in results]
    assert statuses.count("verified") == 1, results
    assert statuses.count("refused") == 1, results
    _refresh(env)
    rows = env.db.query(HITLAction).filter(
        HITLAction.id.in_(["action-1", "action-2"])).all()
    assert len([row for row in rows if row.status == "approved"]) == 1
    assert len([row for row in rows if row.status == "pending"]) == 1


def test_audit_unavailable_after_commit_is_honest(env, monkeypatch):
    user = _make_user(env, secret=TEST_SECRET)
    client = _client(env, user)
    monkeypatch.setattr(audit_service, "log_event", lambda *a, **k: None)
    with freeze_time("2026-01-01 00:00:00"):
        enabled = client.post(
            "/api/auth/2fa/enable",
            json={"code": pyotp.TOTP(TEST_SECRET).now()},
            headers=AUTH_HEADERS)
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["verification"]["status"] == "unavailable"
    assert len(enabled.json()["data"]["backup_codes"]) == 5
    _refresh(env)
    assert env.db.query(User).filter(
        User.id == user.id).one().two_factor_enabled is True
    assert _audits(env, "2fa_enabled") == []

    backup_code = enabled.json()["data"]["backup_codes"][0]
    backup = client.post(
        "/api/auth/2fa/backup/verify",
        json={"code": backup_code}, headers=AUTH_HEADERS)
    assert backup.status_code == 503, backup.text
    assert backup.json()["detail"]["replay"] == "do_not_repeat"
    _refresh(env)
    assert len([row for row in _codes(env, user.id)
                if row.consumed_at is not None]) == 1

    _make_action(env, "action-1", user_id=user.id)
    with freeze_time("2026-01-01 00:00:30"):
        action = client.post(
            "/api/auth/2fa/verify-action/action-1",
            json={"code": pyotp.TOTP(TEST_SECRET).now()},
            headers=AUTH_HEADERS)
    assert action.status_code == 503, action.text
    assert action.json()["detail"]["action_id"] == "action-1"
    _refresh(env)
    assert env.db.query(HITLAction).filter(
        HITLAction.id == "action-1").one().status == "approved"


def test_audit_refuted_after_commit_is_honest(env, monkeypatch):
    user = _make_user(env, secret=TEST_SECRET)
    client = _client(env, user)

    def _wrong_audit(*args, **kwargs):
        with env.Session() as other:
            row = AuditLog(
                id="wrong-audit",
                event_type="update",
                security_level="high",
                threat_level="none",
                user_id="someone-else",
                workspace_id="ws-1",
                action="not-2fa",
                description="wrong",
                success=True,
            )
            other.add(row)
            other.commit()
        return "wrong-audit"

    monkeypatch.setattr(audit_service, "log_event", _wrong_audit)
    with freeze_time("2026-01-01 00:00:00"):
        response = client.post(
            "/api/auth/2fa/enable",
            json={"code": pyotp.TOTP(TEST_SECRET).now()},
            headers=AUTH_HEADERS)
    assert response.status_code == 503, response.text
    assert response.json()["detail"]["verification"]["status"] == "refuted"
    _refresh(env)
    assert env.db.query(User).filter(
        User.id == user.id).one().two_factor_enabled is True


def test_commit_confirmation_loss_is_effect_unknown(env, monkeypatch):
    user = _make_user(env, secret=TEST_SECRET)
    client = _client(env, user)
    original_factory = sessionmaker(bind=env.engine)
    state = {"raised": False}

    @contextlib.contextmanager
    def flaky_session():
        session = original_factory()
        try:
            real_commit = session.commit

            def _commit():
                if not state["raised"]:
                    state["raised"] = True
                    raise RuntimeError("lost confirmation")
                return real_commit()

            session.commit = _commit
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr(
        "core.auth_2fa_write_service.get_db_session", flaky_session)
    with freeze_time("2026-01-01 00:00:00"):
        response = client.post(
            "/api/auth/2fa/enable?operation_id=op-lost",
            json={"code": pyotp.TOTP(TEST_SECRET).now()},
            headers=AUTH_HEADERS)
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "2FA_EFFECT_UNKNOWN"
    assert detail["operation_id"] == "op-lost"
    assert detail["replay"] == "do_not_repeat"


def test_foreign_operation_id_is_refused_without_effect(env):
    user = _make_user(env, secret=TEST_SECRET)
    other = _make_user(env, "other-user", tenant="t2", workspace="ws-2")
    env.db.add(AuthTwoFactorOperation(
        id="op-foreign",
        user_id=other.id,
        tenant_id=other.tenant_id,
        workspace_id=other.workspace_id,
        action="enable",
        factor_revision=0,
        material_fingerprint="foreign",
        status="committed",
        response_json=json.dumps({}),
    ))
    env.db.commit()
    client = _client(env, user)
    with freeze_time("2026-01-01 00:00:00"):
        response = client.post(
            "/api/auth/2fa/enable?operation_id=op-foreign",
            json={"code": pyotp.TOTP(TEST_SECRET).now()},
            headers=AUTH_HEADERS)
    assert response.status_code == 409, response.text
    _refresh(env)
    assert env.db.query(User).filter(
        User.id == user.id).one().two_factor_enabled is False


def test_secrets_and_codes_not_in_audit_or_operation_receipts(env):
    user = _make_user(env, secret=TEST_SECRET)
    client = _client(env, user)
    with freeze_time("2026-01-01 00:00:00"):
        response = client.post(
            "/api/auth/2fa/enable",
            json={"code": pyotp.TOTP(TEST_SECRET).now()},
            headers=AUTH_HEADERS)
    assert response.status_code == 200, response.text
    codes = response.json()["data"]["backup_codes"]
    _refresh(env)
    for audit in _audits(env):
        blob = json.dumps(audit.metadata_json or "")
        for code in codes:
            assert code not in blob
        assert TEST_SECRET not in blob
    for operation in _operations(env, user.id):
        blob = operation.response_json or ""
        for code in codes:
            assert code not in blob
        assert TEST_SECRET not in blob
