"""
TDD bug-hunt tests for the auth territory.

Bugs hunted (each with a failing test first):
1. Password policy bypass: /reset-password accepts empty/short passwords
   (ResetPasswordRequest had no Field constraints).
2. bcrypt 72-byte truncation: passwords >72 bytes are silently truncated,
   so distinct long passwords collide to the same hash (entropy loss +
   "old password still valid after change" for long passwords).
3. Mobile login (POST /api/auth/mobile/login) is not rate limited —
   unbounded password brute-force surface (web login is 10/min).
4. Biometric auth ignores the stored challenge: the client supplies the
   challenge, so a captured (challenge, signature) pair replays; the server
   never checks the challenge it issued at registration.
5. audit_logger._sanitize_params does not recurse into list values, leaking
   credentials nested in lists.
6. app_secrets deletes the plaintext secrets file even when the encrypted
   save fails — permanent secret loss.
"""

from __future__ import annotations

import base64
import json
import os
import secrets

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.auth import get_password_hash, verify_password
from core.auth_endpoints import ResetPasswordRequest, UserCreate
from core.database import get_db
from core.models import MobileDevice, User, UserStatus


@pytest.fixture
def db_session():
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from core.database import Base as _Base
    _Base.metadata.create_all(bind=engine, checkfirst=True)
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def seeded_user(db_session):
    user = User(
        id="bughunt-user-0001",
        email="bughunt@example.com",
        hashed_password=get_password_hash("ValidPass123!"),
        first_name="Bug",
        last_name="Hunt",
        role="member",
        status=UserStatus.ACTIVE.value,
    )
    db_session.add(user)
    db_session.commit()
    return user


# ---------------------------------------------------------------------------
# Bug 1: password policy bypass on /reset-password
# ---------------------------------------------------------------------------


class TestResetPasswordPolicy:
    def test_reset_password_rejects_empty_password(self):
        with pytest.raises(ValidationError):
            ResetPasswordRequest(token="tok", password="")

    def test_reset_password_rejects_short_password(self):
        with pytest.raises(ValidationError):
            ResetPasswordRequest(token="tok", password="short")

    def test_register_rejects_overlong_utf8_password(self):
        with pytest.raises(ValidationError):
            UserCreate(
                email="x@example.com",
                password="\U0001F600" * 30,  # 120 bytes, 30 chars
                first_name="A",
                last_name="B",
            )

    def test_reset_password_accepts_valid_password(self):
        req = ResetPasswordRequest(token="tok", password="ValidPass123!")
        assert req.password == "ValidPass123!"


# ---------------------------------------------------------------------------
# Bug 2: bcrypt 72-byte truncation collisions
# ---------------------------------------------------------------------------


class TestBcryptTruncation:
    def test_get_password_hash_rejects_over_72_bytes(self):
        with pytest.raises(ValueError):
            get_password_hash("A" * 80)

    def test_distinct_long_passwords_must_not_collide(self):
        with pytest.raises(ValueError):
            get_password_hash("A" * 71 + "abc")
        with pytest.raises(ValueError):
            get_password_hash("A" * 71 + "xyz")

    def test_short_passwords_still_hash_and_verify(self):
        hashed = get_password_hash("correct horse battery staple")
        assert verify_password("correct horse battery staple", hashed)
        assert not verify_password("wrong password", hashed)


# ---------------------------------------------------------------------------
# Bug 3: mobile login is not rate limited
# ---------------------------------------------------------------------------


class TestMobileLoginRateLimit:
    def _build_client(self, db_session):
        from api.auth_routes import router as mobile_router
        from core.security.auth_rate_limit import login_rate_limit

        app = FastAPI()
        app.include_router(mobile_router)

        def _get_db():
            yield db_session

        app.dependency_overrides[get_db] = _get_db

        def _blocking_limiter(request):
            raise HTTPException(status_code=429, detail="Too many login attempts")

        app.dependency_overrides[login_rate_limit] = _blocking_limiter
        return TestClient(app)

    def test_mobile_login_is_wired_to_rate_limiter(self, db_session):
        import asyncio
        from unittest.mock import AsyncMock, patch

        client = self._build_client(db_session)
        fake_tokens = {
            "access_token": "fake",
            "refresh_token": "fake",
            "expires_at": "2026-01-01T00:00:00+00:00",
            "token_type": "bearer",
            "user": {"id": "u1", "email": "a@b.com"},
        }
        with patch(
            "api.auth_routes.authenticate_mobile_user",
            new=AsyncMock(return_value=fake_tokens),
        ):
            resp = client.post(
                "/api/auth/mobile/login",
                json={
                    "email": "a@b.com",
                    "password": "ValidPass123!",
                    "device_token": "dev-token",
                    "platform": "ios",
                },
            )
        assert resp.status_code == 429, (
            "mobile login must go through the auth rate limiter — "
            "currently it is an unthrottled brute-force surface"
        )

    def test_mobile_login_succeeds_when_limiter_allows(self, db_session):
        from unittest.mock import AsyncMock, patch

        from api.auth_routes import router as mobile_router

        app = FastAPI()
        app.include_router(mobile_router)

        def _get_db():
            yield db_session

        app.dependency_overrides[get_db] = _get_db
        fake_tokens = {
            "access_token": "fake",
            "refresh_token": "fake",
            "expires_at": "2026-01-01T00:00:00+00:00",
            "token_type": "bearer",
            "user": {"id": "u1", "email": "a@b.com"},
        }
        with TestClient(app) as client, patch(
            "api.auth_routes.authenticate_mobile_user",
            new=AsyncMock(return_value=fake_tokens),
        ):
            resp = client.post(
                "/api/auth/mobile/login",
                json={
                    "email": "a@b.com",
                    "password": "ValidPass123!",
                    "device_token": "dev-token-2",
                    "platform": "android",
                },
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Bug 4: biometric auth does not enforce the stored challenge
# ---------------------------------------------------------------------------


class TestBiometricChallenge:
    @pytest.fixture(scope="session")
    def ec_keypair(self):
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PublicFormat,
        )

        key = ec.generate_private_key(ec.SECP256R1())
        pub_pem = key.public_key().public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        ).decode()

        def sign(challenge: str) -> str:
            sig = key.sign(challenge.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
            return base64.b64encode(sig).decode()

        return pub_pem, sign

    def _build_client(self, db_session, user, device):
        from api.auth_routes import router as mobile_router

        app = FastAPI()
        app.include_router(mobile_router)

        def _get_db():
            yield db_session

        app.dependency_overrides[get_db] = _get_db
        return TestClient(app)

    @pytest.fixture
    def device(self, db_session, seeded_user, ec_keypair):
        pub_pem, _ = ec_keypair
        dev = MobileDevice(
            id="bughunt-device-0001",
            user_id=seeded_user.id,
            device_token="dev-token-biometric",
            platform="ios",
            status="active",
            device_info={
                "biometric_public_key": pub_pem,
                "biometric_challenge": "server-stored-challenge",
            },
        )
        db_session.add(dev)
        db_session.commit()
        return dev

    def test_biometric_auth_rejects_unregistered_challenge(
        self, db_session, seeded_user, device, ec_keypair
    ):
        _, sign = ec_keypair
        client = self._build_client(db_session, seeded_user, device)
        attacker_challenge = "attacker-chosen-challenge"
        resp = client.post(
            "/api/auth/mobile/biometric/authenticate",
            json={
                "device_id": device.id,
                "signature": sign(attacker_challenge),
                "challenge": attacker_challenge,
            },
        )
        assert resp.status_code != 200, (
            "biometric auth accepted a challenge the server never issued — "
            "the stored registration challenge is not enforced (replayable)"
        )

    def test_biometric_auth_accepts_registered_challenge(
        self, db_session, seeded_user, device, ec_keypair
    ):
        _, sign = ec_keypair
        client = self._build_client(db_session, seeded_user, device)
        resp = client.post(
            "/api/auth/mobile/biometric/authenticate",
            json={
                "device_id": device.id,
                "signature": sign("server-stored-challenge"),
                "challenge": "server-stored-challenge",
            },
        )
        assert resp.status_code == 200
        assert resp.json().get("success") is True
        assert resp.json().get("access_token")


# ---------------------------------------------------------------------------
# Bug 5: audit_logger sanitizer leaks secrets inside lists
# ---------------------------------------------------------------------------


class TestAuditSanitizer:
    def test_sanitize_redacts_secrets_in_nested_lists(self):
        from core.audit_logger import IntegrationAuditLog

        log = IntegrationAuditLog(
            connector_id="slack",
            method="send_message",
            params={
                "channel": "general",
                "batch": [
                    {"text": "hello", "token": "SECRET_VALUE"},
                    {"nested": [{"password": "PASS_LEAK"}]},
                ],
            },
        )
        data = log.to_dict()
        serialized = json.dumps(data)
        assert "SECRET_VALUE" not in serialized
        assert "PASS_LEAK" not in serialized

    def test_sanitize_still_keeps_benign_params(self):
        from core.audit_logger import IntegrationAuditLog

        log = IntegrationAuditLog(
            connector_id="slack",
            method="send_message",
            params={"channel": "general", "text": "hello"},
        )
        data = log.to_dict()
        assert data["params"]["channel"] == "general"
        assert data["params"]["text"] == "hello"


# ---------------------------------------------------------------------------
# Bug 6: app_secrets deletes plaintext even when encrypted save fails
# ---------------------------------------------------------------------------


class TestSecretManagerMigration:
    def _make_manager(self, tmp_path, monkeypatch):
        from core.app_secrets import SecretManager

        monkeypatch.setenv("ENCRYPTION_KEY", "test-encryption-key-123")
        m = SecretManager.__new__(SecretManager)
        m._secrets_file = str(tmp_path / "secrets.json")
        m._secrets_encrypted_file = str(tmp_path / "secrets.enc")
        m._secrets = {}
        m._init_encryption()
        return m

    def test_plaintext_kept_when_encrypted_save_fails(
        self, tmp_path, monkeypatch
    ):
        from core.app_secrets import SecretManager

        m = self._make_manager(tmp_path, monkeypatch)
        with open(m._secrets_file, "w") as f:
            json.dump({"api_key": "plain-secret"}, f)

        def _boom(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(m._fernet, "encrypt", _boom)
        m._load_secrets()

        assert os.path.exists(m._secrets_file), (
            "plaintext secrets file must survive a failed encrypted save — "
            "deleting it loses all secrets permanently"
        )

    def test_plaintext_removed_after_successful_migration(
        self, tmp_path, monkeypatch
    ):
        m = self._make_manager(tmp_path, monkeypatch)
        with open(m._secrets_file, "w") as f:
            json.dump({"api_key": "plain-secret"}, f)

        m._load_secrets()

        assert not os.path.exists(m._secrets_file)
        assert os.path.exists(m._secrets_encrypted_file)
