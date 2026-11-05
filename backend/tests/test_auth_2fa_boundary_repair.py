"""Failure-first boundary repair controls for the five auth/2FA routes.

These are the independent verifier probes plus valid twins. The fixture and
helpers are the real scratch-account controls from
``test_oracle_auth_2fa_writes``: real SQLite, real pyotp, real AuditLog and
real HITLAction rows. Only controlled time/rate limiting and deliberate peer
writes are test seams.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pyotp
import pytest
from freezegun import freeze_time
from sqlalchemy import update

import core.auth_2fa_write_service as service
from core.audit_service import audit_service
from core.auth import SECRET_KEY
from core.hitl_service import hitl_service
from core.models import (
    AuditLog,
    AuthTwoFactorBackupCode,
    AuthTwoFactorOperation,
    HITLAction,
    User,
)
from tests.test_oracle_auth_2fa_writes import (
    AUTH_HEADERS,
    TEST_SECRET,
    _client,
    _make_action,
    _make_user,
    env,
)

BACKUP_CODE_A = "AAAA-BBBB-CCCC-DDDD"
BACKUP_CODE_B = "1111-2222-3333-4444"


def _audits(env, action):
    env.db.expire_all()
    return env.db.query(AuditLog).filter(AuditLog.action == action).all()


def _operations(env, user_id):
    env.db.expire_all()
    return env.db.query(AuthTwoFactorOperation).filter(
        AuthTwoFactorOperation.user_id == user_id).all()


def _codes(env, user_id):
    env.db.expire_all()
    return env.db.query(AuthTwoFactorBackupCode).filter(
        AuthTwoFactorBackupCode.user_id == user_id).all()


def _peer_user_change(env, user_id, change):
    with env.Session() as other:
        values = {}
        if change == "workspace":
            values = {"workspace_id": "ws-revoked"}
        elif change == "status":
            values = {"status": "inactive", "is_active": False}
        elif change == "role":
            values = {"role": "viewer"}
        else:
            raise AssertionError(change)
        other.execute(
            update(User).where(User.id == user_id).values(**values))
        other.commit()


# ---------------------------------------------------------------------------
# Contract 1: unverified retries cannot become authentication success
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["backup", "action"])
def test_unverified_authentication_retry_remains_unverified(
        env, monkeypatch, kind):
    user = _make_user(
        env, enabled=True, secret=TEST_SECRET,
        codes=["SYNTHETIC-RECOVERY"], revision=3)
    client = _client(env, user)
    monkeypatch.setattr(audit_service, "log_event", lambda *a, **k: None)
    if kind == "backup":
        path = "/api/auth/2fa/backup/verify"
        code = "SYNTHETIC-RECOVERY"
    else:
        _make_action(env, user_id=user.id)
        path = "/api/auth/2fa/verify-action/action-1"
        with freeze_time("2026-01-01 00:00:30"):
            code = pyotp.TOTP(TEST_SECRET).now()
    with freeze_time("2026-01-01 00:00:30"):
        first = client.post(
            path + "?operation_id=unverified-retry",
            json={"code": code}, headers=AUTH_HEADERS)
        assert first.status_code == 503, first.text
        second = client.post(
            path + "?operation_id=unverified-retry",
            json={"code": code}, headers=AUTH_HEADERS)
    assert second.status_code == 503, second.text
    detail = second.json()["detail"]
    assert detail["verification"]["status"] == "unavailable"
    assert detail["verification"]["replay"] == "do_not_repeat"
    assert detail["operation_id"] == "unverified-retry"
    assert detail["replay"] == "do_not_repeat"
    if kind == "backup":
        assert len([row for row in _codes(env, user.id)
                    if row.consumed_at is not None]) == 1
    else:
        env.db.expire_all()
        action = env.db.query(HITLAction).filter(
            HITLAction.id == "action-1").one()
        assert action.status == "approved"
        assert len(_operations(env, user.id)) == 1


def test_verified_backup_retry_acknowledges_without_new_event(env):
    user = _make_user(
        env, enabled=True, secret=TEST_SECRET,
        codes=[BACKUP_CODE_A, BACKUP_CODE_B])
    client = _client(env, user)
    first = client.post(
        "/api/auth/2fa/backup/verify?operation_id=op-verified-backup",
        json={"code": BACKUP_CODE_A}, headers=AUTH_HEADERS)
    assert first.status_code == 200, first.text
    assert first.json()["verification"]["status"] == "verified"
    retry = client.post(
        "/api/auth/2fa/backup/verify?operation_id=op-verified-backup",
        json={"code": BACKUP_CODE_A}, headers=AUTH_HEADERS)
    assert retry.status_code == 200, retry.text
    body = retry.json()
    assert body["verification"]["status"] == "already_applied"
    assert body["data"]["remaining_codes"] is None
    assert len(_audits(env, "2fa_backup_code_used")) == 1
    assert len([row for row in _codes(env, user.id)
                if row.consumed_at is not None]) == 1


def test_verified_action_retry_acknowledges_without_duplicate_callback(
        env, monkeypatch):
    user = _make_user(env, enabled=True, secret=TEST_SECRET)
    _make_action(env, "action-1", user_id=user.id)
    client = _client(env, user)
    callbacks = []

    async def callback(row):
        callbacks.append(row.id)

    monkeypatch.setattr(hitl_service, "_resume_workflow", callback)
    with freeze_time("2026-01-01 00:00:00"):
        code = pyotp.TOTP(TEST_SECRET).now()
        first = client.post(
            "/api/auth/2fa/verify-action/action-1?operation_id=op-verified-action",
            json={"code": code}, headers=AUTH_HEADERS)
        retry = client.post(
            "/api/auth/2fa/verify-action/action-1?operation_id=op-verified-action",
            json={"code": code}, headers=AUTH_HEADERS)
    assert first.status_code == 200, first.text
    assert first.json()["verification"]["status"] == "verified"
    assert retry.status_code == 200, retry.text
    assert retry.json()["verification"]["status"] == "already_applied"
    assert callbacks == ["action-1"]
    assert len(_audits(env, "hitl_action_verified_2fa")) == 1
    assert len(_operations(env, user.id)) == 1


def test_action_replay_after_material_change_is_unverified(
        env, monkeypatch):
    user = _make_user(env, enabled=True, secret=TEST_SECRET)
    _make_action(env, "action-1", user_id=user.id)
    client = _client(env, user)
    callbacks = []

    async def callback(row):
        callbacks.append(row.id)

    monkeypatch.setattr(hitl_service, "_resume_workflow", callback)
    with freeze_time("2026-01-01 00:00:00"):
        code = pyotp.TOTP(TEST_SECRET).now()
        first = client.post(
            "/api/auth/2fa/verify-action/action-1?operation_id=op-replay-material",
            json={"code": code}, headers=AUTH_HEADERS)
    assert first.status_code == 200, first.text
    with env.Session() as other:
        other.execute(
            update(HITLAction).where(HITLAction.id == "action-1").values(
                params={"recipient": "changed-after-approval"}))
        other.commit()
    retry = client.post(
        "/api/auth/2fa/verify-action/action-1?operation_id=op-replay-material",
        json={"code": code}, headers=AUTH_HEADERS)
    assert retry.status_code == 503, retry.text
    assert retry.json()["detail"]["verification"]["status"] == "refuted"
    assert callbacks == ["action-1"]


def test_backup_replay_after_actor_deactivation_is_unverified(env):
    user = _make_user(
        env, enabled=True, secret=TEST_SECRET, codes=[BACKUP_CODE_A])
    client = _client(env, user)
    first = client.post(
        "/api/auth/2fa/backup/verify?operation_id=op-deactivated",
        json={"code": BACKUP_CODE_A}, headers=AUTH_HEADERS)
    assert first.status_code == 200, first.text
    _peer_user_change(env, user.id, "status")
    retry = client.post(
        "/api/auth/2fa/backup/verify?operation_id=op-deactivated",
        json={"code": BACKUP_CODE_A}, headers=AUTH_HEADERS)
    assert retry.status_code == 503, retry.text
    assert retry.json()["detail"]["verification"]["status"] == "refuted"


# ---------------------------------------------------------------------------
# Contract 2: complete audit evidence only
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_field", [
    "workspace",
    "tenant_missing",
    "tenant_type",
    "resource",
    "factor_revision",
    "factor_revision_type",
    "target_id",
    "target_id_missing",
    "operation_id_missing",
    "operation_id_type",
    "event_type",
    "security_level",
    "success",
])
def test_audit_must_match_complete_authorized_operation(
        env, monkeypatch, bad_field):
    user = _make_user(
        env, enabled=True, secret=TEST_SECRET,
        codes=["SYNTHETIC-RECOVERY"], revision=3)

    def incorrect_audit(db, **kwargs):
        metadata = dict(kwargs["metadata"])
        workspace = kwargs["workspace_id"]
        resource = kwargs["resource"]
        event_type = "update"
        security_level = "high"
        success = True
        if bad_field == "workspace":
            workspace = "default"
        elif bad_field == "tenant_missing":
            metadata.pop("tenant_id", None)
        elif bad_field == "tenant_type":
            metadata["tenant_id"] = 1
        elif bad_field == "resource":
            resource = "user:other-user:2fa"
        elif bad_field == "factor_revision":
            metadata["factor_revision"] = 999
        elif bad_field == "factor_revision_type":
            metadata["factor_revision"] = "3"
        elif bad_field == "target_id":
            metadata["target_id"] = "different-code-record"
        elif bad_field == "target_id_missing":
            metadata.pop("target_id", None)
        elif bad_field == "operation_id_missing":
            metadata.pop("operation_id", None)
        elif bad_field == "operation_id_type":
            metadata["operation_id"] = 123
        elif bad_field == "event_type":
            event_type = "create"
        elif bad_field == "security_level":
            security_level = "low"
        elif bad_field == "success":
            success = False
        audit_id = "verifier-audit-" + uuid.uuid4().hex
        db.add(AuditLog(
            id=audit_id,
            event_type=event_type,
            security_level=security_level,
            threat_level="none",
            user_id=kwargs["user_id"],
            workspace_id=workspace,
            action=kwargs["action"],
            description="controlled mismatch",
            success=success,
            resource=resource,
            metadata_json=json.dumps(metadata),
        ))
        db.commit()
        return audit_id

    monkeypatch.setattr(audit_service, "log_event", incorrect_audit)
    response = _client(env, user).post(
        "/api/auth/2fa/backup/verify",
        json={"code": "SYNTHETIC-RECOVERY"}, headers=AUTH_HEADERS)
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["verification"]["status"] in ("unavailable", "refuted")


def test_complete_audit_twin_verifies(env):
    user = _make_user(
        env, enabled=True, secret=TEST_SECRET, codes=[BACKUP_CODE_A])
    response = _client(env, user).post(
        "/api/auth/2fa/backup/verify",
        json={"code": BACKUP_CODE_A}, headers=AUTH_HEADERS)
    assert response.status_code == 200, response.text
    assert response.json()["verification"]["status"] == "verified"
    assert len(_audits(env, "2fa_backup_code_used")) == 1


# ---------------------------------------------------------------------------
# Contract 3: authority / action material changes before claim
# ---------------------------------------------------------------------------

def _action_change(env, action_id, change):
    with env.Session() as other:
        if change == "required_role":
            values = {
                "required_role": "admin",
                "context_snapshot": {"required_role": "admin"},
            }
        elif change == "action_material":
            values = {"params": {"recipient": "changed-before-approval"}}
        elif change == "action_priority":
            values = {"priority": "URGENT"}
        else:
            raise AssertionError(change)
        other.execute(
            update(HITLAction).where(HITLAction.id == action_id).values(
                **values))
        other.commit()


@pytest.mark.parametrize("change", [
    "user_workspace",
    "user_status",
    "user_role",
    "required_role",
    "action_material",
    "action_priority",
])
def test_authority_change_before_action_claim_refuses_without_effect(
        env, monkeypatch, change):
    user = _make_user(env, enabled=True, secret=TEST_SECRET, revision=3)
    action = _make_action(env, user_id=user.id)
    callbacks = []

    async def callback(row):
        callbacks.append(row.id)

    monkeypatch.setattr(hitl_service, "_resume_workflow", callback)
    original_verify = pyotp.TOTP.verify
    moved = []

    def verify_then_change(self, *args, **kwargs):
        valid = original_verify(self, *args, **kwargs)
        if valid and not moved:
            if change == "user_workspace":
                _peer_user_change(env, user.id, "workspace")
            elif change == "user_status":
                _peer_user_change(env, user.id, "status")
            elif change == "user_role":
                _peer_user_change(env, user.id, "role")
            else:
                _action_change(env, action.id, change)
            moved.append(True)
        return valid

    monkeypatch.setattr(pyotp.TOTP, "verify", verify_then_change)
    with freeze_time("2026-01-01 00:00:30"):
        code = pyotp.TOTP(TEST_SECRET).now()
        response = _client(env, user).post(
            "/api/auth/2fa/verify-action/action-1",
            json={"code": code}, headers=AUTH_HEADERS)
    assert moved
    env.db.expire_all()
    persisted = env.db.query(HITLAction).filter_by(id=action.id).one()
    assert response.status_code == 409, response.text
    assert persisted.status == "pending"
    assert _operations(env, user.id) == []
    assert callbacks == []


def test_authority_valid_twin_approves_once(env, monkeypatch):
    user = _make_user(env, enabled=True, secret=TEST_SECRET)
    _make_action(env, "action-1", user_id=user.id)
    callbacks = []

    async def callback(row):
        callbacks.append(row.id)

    monkeypatch.setattr(hitl_service, "_resume_workflow", callback)
    with freeze_time("2026-01-01 00:00:30"):
        code = pyotp.TOTP(TEST_SECRET).now()
        response = _client(env, user).post(
            "/api/auth/2fa/verify-action/action-1",
            json={"code": code}, headers=AUTH_HEADERS)
    assert response.status_code == 200, response.text
    assert response.json()["verification"]["status"] == "verified"
    env.db.expire_all()
    action = env.db.query(HITLAction).filter(
        HITLAction.id == "action-1").one()
    assert action.status == "approved"
    assert action.reviewed_by == user.id
    assert action.reviewed_at is not None
    assert len(_operations(env, user.id)) == 1
    assert callbacks == ["action-1"]


@pytest.mark.parametrize("route", ["setup", "enable", "disable", "backup"])
def test_factor_authority_change_before_claim_refuses_without_effect(
        env, monkeypatch, route):
    if route == "setup":
        user = _make_user(env)
    elif route == "enable":
        user = _make_user(env, secret=TEST_SECRET)
    else:
        user = _make_user(
            env, enabled=True, secret=TEST_SECRET, codes=[BACKUP_CODE_A])
    client = _client(env, user)
    moved = []

    if route == "setup":
        real_base32 = pyotp.random_base32

        def change_then_secret():
            if not moved:
                _peer_user_change(env, user.id, "workspace")
                moved.append(True)
            return real_base32()

        monkeypatch.setattr(pyotp, "random_base32", change_then_secret)
        response = client.post("/api/auth/2fa/setup", headers=AUTH_HEADERS)
    elif route in ("enable", "disable"):
        original_verify = pyotp.TOTP.verify

        def verify_then_change(self, *args, **kwargs):
            valid = original_verify(self, *args, **kwargs)
            if valid and not moved:
                _peer_user_change(env, user.id, "status")
                moved.append(True)
            return valid

        monkeypatch.setattr(pyotp.TOTP, "verify", verify_then_change)
        with freeze_time("2026-01-01 00:00:00"):
            code = pyotp.TOTP(TEST_SECRET).now()
            response = client.post(
                f"/api/auth/2fa/{route}", json={"code": code},
                headers=AUTH_HEADERS)
    else:
        real_fingerprint = service._code_fingerprint

        def fingerprint_then_change(user_id, code):
            if not moved:
                _peer_user_change(env, user.id, "role")
                moved.append(True)
            return real_fingerprint(user_id, code)

        monkeypatch.setattr(
            service, "_code_fingerprint", fingerprint_then_change)
        response = client.post(
            "/api/auth/2fa/backup/verify",
            json={"code": BACKUP_CODE_A}, headers=AUTH_HEADERS)

    assert moved
    assert response.status_code == 409, response.text
    env.db.expire_all()
    persisted = env.db.query(User).filter(User.id == user.id).one()
    assert _operations(env, user.id) == []
    if route == "setup":
        assert persisted.two_factor_secret is None
    elif route == "enable":
        assert persisted.two_factor_enabled is False
        assert _codes(env, user.id) == []
    elif route == "disable":
        assert persisted.two_factor_enabled is True
        assert persisted.two_factor_secret == TEST_SECRET
    else:
        assert persisted.two_factor_backup_codes == [BACKUP_CODE_A]
        assert [row for row in _codes(env, user.id)
                if row.consumed_at is not None] == []


# ---------------------------------------------------------------------------
# Contract 4: no secret / SQL parameters in responses or logs
# ---------------------------------------------------------------------------

def test_database_error_never_exposes_factor_secret(
        env, monkeypatch, caplog):
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session
    from sqlite3 import OperationalError as SQLiteOperationalError

    user = _make_user(env)
    original = Session.commit
    failed = []

    def fail_sensitive_commit(db):
        if not failed and any(
                isinstance(row, AuthTwoFactorOperation) for row in db.new):
            failed.append(True)
            raise OperationalError(
                "UPDATE users SET two_factor_secret=?",
                (TEST_SECRET,),
                SQLiteOperationalError("controlled lost confirmation"),
            )
        return original(db)

    monkeypatch.setattr(Session, "commit", fail_sensitive_commit)
    monkeypatch.setattr(pyotp, "random_base32", lambda: TEST_SECRET)
    response = _client(env, user).post(
        "/api/auth/2fa/setup", headers=AUTH_HEADERS)
    assert failed
    assert TEST_SECRET not in response.text
    assert TEST_SECRET not in caplog.text
    assert "UPDATE users" not in response.text
    assert "UPDATE users" not in caplog.text
    assert response.json()["detail"]["error"]["code"] == "2FA_EFFECT_UNKNOWN"
    assert response.json()["detail"]["verification"]["error"] == (
        "COMMIT_OUTCOME_UNKNOWN")


# ---------------------------------------------------------------------------
# Concurrent different-code consumption must not resurrect consumed codes
# ---------------------------------------------------------------------------

def test_stale_legacy_mirror_does_not_retain_consumed_codes(env):
    user = _make_user(
        env, enabled=True, secret=TEST_SECRET,
        codes=[BACKUP_CODE_A, BACKUP_CODE_B])
    env.db.add(AuthTwoFactorBackupCode(
        user_id=user.id,
        tenant_id=user.tenant_id,
        workspace_id=user.workspace_id,
        code_fingerprint=service._code_fingerprint(user.id, BACKUP_CODE_A),
        factor_revision=0,
        consumed_at=datetime.now(timezone.utc),
        operation_id="older-consumed-operation",
    ))
    env.db.add(AuthTwoFactorBackupCode(
        user_id=user.id,
        tenant_id=user.tenant_id,
        workspace_id=user.workspace_id,
        code_fingerprint=service._code_fingerprint(user.id, BACKUP_CODE_B),
        factor_revision=0,
    ))
    env.db.commit()

    response = _client(env, user).post(
        "/api/auth/2fa/backup/verify",
        json={"code": BACKUP_CODE_B}, headers=AUTH_HEADERS)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["remaining_codes"] == 0
    assert response.json()["verification"]["status"] == "verified"

    env.db.expire_all()
    refreshed = env.db.query(User).filter(User.id == user.id).one()
    assert refreshed.two_factor_backup_codes == []
    rows = _codes(env, user.id)
    assert len(rows) == 2
    assert all(row.consumed_at is not None for row in rows)


def test_concurrent_different_backup_codes_stay_consistent(env):
    user = _make_user(
        env, enabled=True, secret=TEST_SECRET,
        codes=[BACKUP_CODE_A, BACKUP_CODE_B])
    barrier = threading.Barrier(2)

    def _consume(operation_id, code):
        barrier.wait()
        return service.verify_backup_code_verified(
            user_id=user.id,
            code=code,
            request=None,
            operation_id=operation_id,
            audit_logger=audit_service,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda pair: _consume(pair[0], pair[1]),
            [("op-different-1", BACKUP_CODE_A),
             ("op-different-2", BACKUP_CODE_B)],
        ))
    statuses = [result["status"] for result in results]
    verified_count = statuses.count("verified")
    assert verified_count in (1, 2), results
    assert statuses.count("refused") == 2 - verified_count, results

    env.db.expire_all()
    refreshed = env.db.query(User).filter(User.id == user.id).one()
    current = list(refreshed.two_factor_backup_codes or [])
    rows = _codes(env, user.id)
    consumed = [row for row in rows if row.consumed_at is not None]
    expected_fingerprints = {
        code: hmac.new(
            str(SECRET_KEY).encode(), f"code|{user.id}|{code}".encode(),
            hashlib.sha256).hexdigest()
        for code in (BACKUP_CODE_A, BACKUP_CODE_B)
    }
    consumed_codes = {
        code for code, fingerprint in expected_fingerprints.items()
        if any(row.code_fingerprint == fingerprint for row in consumed)
    }
    assert not (consumed_codes & set(current)), (consumed_codes, current)
    assert len(consumed) == statuses.count("verified")
    assert len(current) == 2 - len(consumed_codes)
    assert len(_audits(env, "2fa_backup_code_used")) == len(consumed)

    if statuses.count("refused") == 1:
        refused_code = (
            BACKUP_CODE_B if BACKUP_CODE_A in consumed_codes
            else BACKUP_CODE_A)
        retry = _client(env, user).post(
            "/api/auth/2fa/backup/verify?operation_id=op-different-retry",
            json={"code": refused_code}, headers=AUTH_HEADERS)
        assert retry.status_code == 200, retry.text
        assert retry.json()["verification"]["status"] == "verified"
