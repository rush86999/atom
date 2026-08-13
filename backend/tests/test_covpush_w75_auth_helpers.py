"""Coverage wave 75 — core/auth_helpers.py (63% → 95%+).

Closes the token lifecycle surface: verify_jwt_token (valid/expired/malformed/
missing-sub/no-secret/emergency-bypass paths), require_authenticated_user +
get_optional_user (default fallback, db-validated, no-db minimal), revoke/
revoke-all/track/cleanup helpers including error paths. Real in-memory SQLite
for the DB-backed helpers; jose jwt.decode is mocked for deterministic paths.
"""
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from jose import ExpiredSignatureError, JWTError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.auth_helpers as ah
from core.database import Base
from core.models import ActiveToken, RevokedToken, User, UserRole, UserStatus

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def user(db):
    u = User(
        email="admin@atom.ai",
        hashed_password="x",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN.value,
        status=UserStatus.ACTIVE.value,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _payload(**overrides):
    p = {
        "sub": "user-1",
        "jti": "jti-1",
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
    }
    p.update(overrides)
    return p


class TestVerifyJwtToken:
    def test_valid_token(self):
        with patch.object(ah.jwt, "decode", return_value=_payload()) as dec:
            out = ah.verify_jwt_token("tok")
        dec.assert_called_once()
        assert out["sub"] == "user-1"

    def test_missing_sub_claim(self):
        with patch.object(ah.jwt, "decode", return_value={"jti": "j1"}):
            with pytest.raises(HTTPException) as ei:
                ah.verify_jwt_token("tok")
        assert ei.value.status_code == 401
        assert "missing subject" in ei.value.detail

    def test_expired_token(self):
        with patch.object(ah.jwt, "decode", side_effect=ExpiredSignatureError()):
            with pytest.raises(HTTPException) as ei:
                ah.verify_jwt_token("tok")
        assert ei.value.status_code == 401
        assert "expired" in ei.value.detail.lower()

    def test_invalid_token(self):
        with patch.object(ah.jwt, "decode", side_effect=JWTError("bad")):
            with pytest.raises(HTTPException) as ei:
                ah.verify_jwt_token("tok")
        assert ei.value.status_code == 401
        assert ei.value.detail == "Invalid token"

    def test_invalid_token_emergency_bypass(self):
        with patch.object(ah.jwt, "decode", side_effect=JWTError("bad")), \
             patch.dict(os.environ, {"EMERGENCY_GOVERNANCE_BYPASS": "true"}, clear=True):
            out = ah.verify_jwt_token("tok")
        assert out["user_id"] == "emergency_user"
        assert out["bypass"] is True

    def test_no_secret_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(HTTPException) as ei:
                ah.verify_jwt_token("tok")
        assert ei.value.status_code == 500
        assert "secret" in ei.value.detail.lower()

    def test_no_secret_but_emergency_bypass(self):
        # emergency bypass skips the no-secret 500 and falls through to decode;
        # the decode failure (None key) is then rescued by the bypass path.
        with patch.dict(os.environ, {"EMERGENCY_GOVERNANCE_BYPASS": "true"}, clear=True):
            out = ah.verify_jwt_token("tok")
        assert out["bypass"] is True

    def test_unexpected_error_raises_401(self):
        with patch.object(ah.jwt, "decode", side_effect=RuntimeError("boom")):
            with pytest.raises(HTTPException) as ei:
                ah.verify_jwt_token("tok")
        assert ei.value.status_code == 401
        assert ei.value.detail == "Authentication failed"

    def test_unexpected_error_emergency_bypass(self):
        with patch.object(ah.jwt, "decode", side_effect=RuntimeError("boom")), \
             patch.dict(os.environ, {"EMERGENCY_GOVERNANCE_BYPASS": "true"}, clear=True):
            out = ah.verify_jwt_token("tok")
        assert out["bypass"] is True

    def test_http_exception_preserved_not_swallowed(self):
        # verify_jwt_token must not wrap its own HTTPException in "Authentication failed"
        with patch.object(ah.jwt, "decode", side_effect=JWTError("x")):
            pass  # JWTError path already covered; HTTPException preservation via missing sub:
        with patch.object(ah.jwt, "decode", side_effect=HTTPException(401, "custom")):
            with pytest.raises(HTTPException) as ei:
                ah.verify_jwt_token("tok")
        assert ei.value.detail == "custom"


class TestRequireAuthenticatedUser:
    async def test_missing_user_id(self, db):
        with pytest.raises(HTTPException) as ei:
            await ah.require_authenticated_user(None, db)
        assert ei.value.status_code == 401

    async def test_default_user_not_allowed(self, db):
        with pytest.raises(HTTPException) as ei:
            await ah.require_authenticated_user("default_user", db)
        assert ei.value.status_code == 401

    async def test_allow_default_with_admin_user(self, db, user):
        u = await ah.require_authenticated_user("default_user", db, allow_default=True)
        assert u.email == "admin@atom.ai"

    async def test_allow_default_without_admin(self, db):
        with pytest.raises(HTTPException) as ei:
            await ah.require_authenticated_user("default_user", db, allow_default=True)
        assert ei.value.status_code == 401

    async def test_allow_default_no_db(self, db):
        with pytest.raises(HTTPException) as ei:
            await ah.require_authenticated_user("default_user", None, allow_default=True)
        assert ei.value.status_code == 401

    async def test_user_found_in_db(self, db, user):
        u = await ah.require_authenticated_user(user.id, db)
        assert u.id == user.id

    async def test_user_not_found_in_db(self, db):
        with pytest.raises(HTTPException) as ei:
            await ah.require_authenticated_user("missing-id", db)
        assert ei.value.status_code == 404
        assert "missing-id" in ei.value.detail

    async def test_no_db_returns_minimal_user(self, db):
        u = await ah.require_authenticated_user("some-id", None)
        assert u.id == "some-id"
        assert u.email == ""


class TestGetOptionalUser:
    async def test_none_and_default(self, db):
        assert await ah.get_optional_user(None, db) is None
        assert await ah.get_optional_user("default_user", db) is None

    async def test_with_db_found(self, db, user):
        u = await ah.get_optional_user(user.id, db)
        assert u.id == user.id

    async def test_with_db_missing(self, db):
        assert await ah.get_optional_user("nope", db) is None

    async def test_without_db(self, db):
        u = await ah.get_optional_user("xyz")
        assert u.id == "xyz"


class TestValidateUserContext:
    def test_missing(self):
        with pytest.raises(HTTPException) as ei:
            ah.validate_user_context(None, "process payment")
        assert ei.value.status_code == 401
        assert "process payment" in ei.value.detail

    def test_default_user(self):
        with pytest.raises(HTTPException) as ei:
            ah.validate_user_context("default_user", "send email")
        assert ei.value.status_code == 401

    def test_valid(self):
        ah.validate_user_context("user-1", "process payment")


class TestRevokeToken:
    def test_revoke_new(self, db):
        exp = datetime.now(timezone.utc) + timedelta(hours=1)
        assert ah.revoke_token("jti-new", exp, db, user_id="u1", revocation_reason="logout") is True
        row = db.query(RevokedToken).filter_by(jti="jti-new").first()
        assert row.user_id == "u1"
        assert row.reason == "logout"

    def test_revoke_duplicate_returns_false(self, db):
        exp = datetime.now(timezone.utc) + timedelta(hours=1)
        ah.revoke_token("jti-dup", exp, db, user_id="u1")
        assert ah.revoke_token("jti-dup", exp, db, user_id="u1") is False

    def test_revoke_default_reason(self, db):
        exp = datetime.now(timezone.utc) + timedelta(hours=1)
        ah.revoke_token("jti-def", exp, db, user_id="u1")
        assert db.query(RevokedToken).filter_by(jti="jti-def").first().reason == "logout"

    def test_revoke_db_error_500(self, db):
        db.commit = MagicMock(side_effect=RuntimeError("disk full"))
        db.rollback = MagicMock()
        with pytest.raises(HTTPException) as ei:
            ah.revoke_token("jti-err", datetime.now(timezone.utc), db, user_id="u1")
        assert ei.value.status_code == 500
        db.rollback.assert_called_once()


class TestRevokeAllUserTokens:
    def test_revoke_all(self, db, user):
        for jti in ("t1", "t2"):
            db.add(ActiveToken(jti=jti, user_id=user.id,
                               expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        db.commit()
        count = ah.revoke_all_user_tokens(user.id, db, revocation_reason="password_change")
        assert count == 2
        assert db.query(ActiveToken).filter_by(user_id=user.id).count() == 0
        assert db.query(RevokedToken).filter_by(user_id=user.id).count() == 2

    def test_revoke_all_except_jti(self, db, user):
        for jti in ("keep", "drop"):
            db.add(ActiveToken(jti=jti, user_id=user.id,
                               expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        db.commit()
        count = ah.revoke_all_user_tokens(user.id, db, except_jti="keep")
        assert count == 1
        assert db.query(ActiveToken).filter_by(jti="keep").first() is not None
        assert db.query(RevokedToken).filter_by(jti="drop").first() is not None

    def test_no_active_tokens(self, db, user):
        assert ah.revoke_all_user_tokens(user.id, db) == 0

    def test_already_revoked_skipped(self, db, user):
        db.add(ActiveToken(jti="t1", user_id=user.id,
                           expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        db.commit()
        ah.revoke_all_user_tokens(user.id, db)
        assert ah.revoke_all_user_tokens(user.id, db) == 0

    def test_already_revoked_entry_skipped_in_loop(self, db, user):
        # ActiveToken exists but a RevokedToken with the same jti already exists
        db.add(ActiveToken(jti="t-dup", user_id=user.id,
                           expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        db.add(RevokedToken(jti="t-dup", user_id=user.id,
                            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        db.commit()
        count = ah.revoke_all_user_tokens(user.id, db)
        assert count == 0  # skipped, not double-revoked
        assert db.query(ActiveToken).filter_by(jti="t-dup").first() is not None

    def test_default_reason_admin_action(self, db, user):
        db.add(ActiveToken(jti="t1", user_id=user.id,
                           expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        db.commit()
        ah.revoke_all_user_tokens(user.id, db)
        assert db.query(RevokedToken).filter_by(jti="t1").first().reason == "admin_action"

    def test_error_500(self, db, user):
        db.add(ActiveToken(jti="t1", user_id=user.id,
                           expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        db.commit()
        db.commit = MagicMock(side_effect=RuntimeError("boom"))
        with pytest.raises(HTTPException) as ei:
            ah.revoke_all_user_tokens(user.id, db)
        assert ei.value.status_code == 500


class TestTrackActiveToken:
    def test_track_new(self, db, user):
        exp = datetime.now(timezone.utc) + timedelta(hours=1)
        assert ah.track_active_token("jti-a", user.id, exp, db,
                                     issued_ip="1.2.3.4",
                                     issued_user_agent="test-agent") is True
        row = db.query(ActiveToken).filter_by(jti="jti-a").first()
        assert row.issued_ip == "1.2.3.4"
        assert row.issued_user_agent == "test-agent"

    def test_track_duplicate_false(self, db, user):
        exp = datetime.now(timezone.utc) + timedelta(hours=1)
        ah.track_active_token("jti-b", user.id, exp, db)
        assert ah.track_active_token("jti-b", user.id, exp, db) is False

    def test_track_error_500(self, db, user):
        db.commit = MagicMock(side_effect=RuntimeError("boom"))
        db.rollback = MagicMock()
        with pytest.raises(HTTPException) as ei:
            ah.track_active_token("jti-c", user.id, datetime.now(timezone.utc), db)
        assert ei.value.status_code == 500
        db.rollback.assert_called_once()


class TestCleanup:
    def test_cleanup_expired_revoked(self, db):
        past = datetime.now(timezone.utc) - timedelta(hours=48)
        future = datetime.now(timezone.utc) + timedelta(hours=48)
        db.add(RevokedToken(jti="old", user_id="u1", expires_at=past))
        db.add(RevokedToken(jti="new", user_id="u2", expires_at=future))
        db.commit()
        assert ah.cleanup_expired_revoked_tokens(db) == 1
        assert db.query(RevokedToken).filter_by(jti="new").first() is not None

    def test_cleanup_expired_revoked_error_returns_zero(self, db):
        db.commit = MagicMock(side_effect=RuntimeError("boom"))
        db.rollback = MagicMock()
        assert ah.cleanup_expired_revoked_tokens(db) == 0
        db.rollback.assert_called_once()

    def test_cleanup_expired_active(self, db, user):
        past = datetime.now(timezone.utc) - timedelta(hours=2)
        future = datetime.now(timezone.utc) + timedelta(hours=2)
        db.add(ActiveToken(jti="old", user_id=user.id, expires_at=past))
        db.add(ActiveToken(jti="new", user_id=user.id, expires_at=future))
        db.commit()
        assert ah.cleanup_expired_active_tokens(db) == 1
        assert db.query(ActiveToken).filter_by(jti="new").first() is not None

    def test_cleanup_expired_active_error_returns_zero(self, db):
        db.commit = MagicMock(side_effect=RuntimeError("boom"))
        db.rollback = MagicMock()
        assert ah.cleanup_expired_active_tokens(db) == 0
        db.rollback.assert_called_once()
