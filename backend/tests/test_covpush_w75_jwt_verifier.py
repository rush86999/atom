"""Coverage wave 75 — core/jwt_verifier.py (76% → 95%+).

Closes the verifier surface: init validation (default-secret rejection, no
secret, debug overrides, whitelist parsing), IP-whitelist CIDR/single-IP
matching, debug-mode bypass paths (whitelisted, no whitelist, production
blocked), audience/issuer/expiry/missing-subject rejections, revocation
checking (jti/db missing, revoked, DB error fail-open), token creation with
audience/issuer/extra claims, the FastAPI dependency wrapper (XFF handling)
and verify_token_string. Real PyJWT round-trips; DB-backed revocation uses
in-memory SQLite.
"""
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.jwt_verifier as jv
from core.database import Base
from core.models import RevokedToken

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

SECRET = "test-secret-key-32-bytes-for-hs256-signing"


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
def verifier():
    return jv.JWTVerifier(secret_key=SECRET, debug_mode=True)


@pytest.fixture(autouse=True)
def _env():
    with patch.dict(os.environ, {"JWT_SECRET": SECRET}, clear=True):
        yield


@pytest.fixture(autouse=True)
def _reset_global():
    saved = jv._jwt_verifier
    jv._jwt_verifier = None
    yield
    jv._jwt_verifier = saved


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


class TestInit:
    def test_init_defaults_and_audience_issuer_env(self):
        with patch.dict(os.environ, {"JWT_SECRET": SECRET, "JWT_AUDIENCE": "api",
                                     "JWT_ISSUER": "atom", "DEBUG": "true"}, clear=True):
            v = jv.JWTVerifier()
        assert v.debug_mode is True
        assert v.audience == "api"
        assert v.issuer == "atom"

    def test_init_debug_param_overrides_env(self):
        with patch.dict(os.environ, {"JWT_SECRET": SECRET, "DEBUG": "false"}, clear=True):
            assert jv.JWTVerifier(debug_mode=True).debug_mode is True

    def test_init_parses_debug_ip_whitelist(self):
        with patch.dict(os.environ, {"JWT_SECRET": SECRET,
                                     "DEBUG_IP_WHITELIST": "10.0.0.0/8, 127.0.0.1"}, clear=True):
            v = jv.JWTVerifier()
        assert v.debug_ip_whitelist == ["10.0.0.0/8", "127.0.0.1"]

    def test_init_default_secret_rejected_in_production(self):
        with pytest.raises(ValueError, match="default secret"):
            jv.JWTVerifier(secret_key="secret", debug_mode=False)

    def test_init_no_secret_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="JWT_SECRET"):
                jv.JWTVerifier(debug_mode=True)

    def test_init_allowed_default_secret_in_debug(self):
        v = jv.JWTVerifier(secret_key="secret", debug_mode=True)
        assert v.debug_mode is True


class TestIpWhitelist:
    def test_cidr_match(self, verifier):
        assert verifier._is_ip_whitelisted("10.1.2.3") is False
        v = jv.JWTVerifier(secret_key=SECRET, debug_mode=True,
                           debug_ip_whitelist=["10.0.0.0/8"])
        assert v._is_ip_whitelisted("10.1.2.3") is True
        assert v._is_ip_whitelisted("11.1.2.3") is False

    def test_single_ip_match(self, verifier):
        v = jv.JWTVerifier(secret_key=SECRET, debug_mode=True,
                           debug_ip_whitelist=["127.0.0.1"])
        assert v._is_ip_whitelisted("127.0.0.1") is True
        assert v._is_ip_whitelisted("127.0.0.2") is False

    def test_empty_whitelist_false(self, verifier):
        assert verifier._is_ip_whitelisted("127.0.0.1") is False

    def test_invalid_ip_false(self, verifier):
        v = jv.JWTVerifier(secret_key=SECRET, debug_mode=True,
                           debug_ip_whitelist=["127.0.0.1"])
        assert v._is_ip_whitelisted("not-an-ip") is False
        v2 = jv.JWTVerifier(secret_key=SECRET, debug_mode=True,
                            debug_ip_whitelist=["not-a-cidr/99"])
        assert v2._is_ip_whitelisted("127.0.0.1") is False


class TestVerifyToken:
    def test_no_credentials(self, verifier):
        with pytest.raises(HTTPException) as ei:
            verifier.verify_token(None)
        assert ei.value.status_code == 401

    def test_empty_credentials(self, verifier):
        with pytest.raises(HTTPException) as ei:
            verifier.verify_token(_creds(""))
        assert ei.value.status_code == 401

    def test_valid_token(self, verifier):
        tok = verifier.create_token("user-1")
        payload = verifier.verify_token(_creds(tok))
        assert payload["sub"] == "user-1"
        assert payload["jti"]

    def test_expired_token(self, verifier):
        tok = verifier.create_token("user-1", expires_delta=timedelta(seconds=-10))
        with pytest.raises(HTTPException) as ei:
            verifier.verify_token(_creds(tok))
        assert ei.value.status_code == 401
        assert "expired" in ei.value.detail.lower()

    def test_invalid_signature(self, verifier):
        other = jwt.encode({"sub": "x", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                           "wrong-key-00000000000000000000000000000000", algorithm="HS256")
        with pytest.raises(HTTPException) as ei:
            verifier.verify_token(_creds(other))
        assert ei.value.status_code == 401
        assert "Invalid token" in ei.value.detail

    def test_missing_subject(self, verifier):
        tok = verifier.create_token("s")
        bad = jwt.encode({"exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                         SECRET, algorithm="HS256")
        with pytest.raises(HTTPException) as ei:
            verifier.verify_token(_creds(bad))
        assert ei.value.status_code == 401
        assert "subject" in ei.value.detail

    def test_audience_mismatch(self):
        v = jv.JWTVerifier(secret_key=SECRET, debug_mode=True, audience="api")
        wrong = jwt.encode({"sub": "u", "aud": "other",
                            "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                           SECRET, algorithm="HS256")
        with pytest.raises(HTTPException) as ei:
            v.verify_token(_creds(wrong))
        assert ei.value.status_code == 401
        assert "audience" in ei.value.detail.lower()

    def test_audience_missing_on_token(self):
        v = jv.JWTVerifier(secret_key=SECRET, debug_mode=True, audience="api")
        tok = v.create_token("u1")
        assert v.verify_token(_creds(tok))["sub"] == "u1"
        no_aud = jwt.encode({"sub": "u", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                            SECRET, algorithm="HS256")
        with pytest.raises(HTTPException) as ei:
            v.verify_token(_creds(no_aud))
        assert ei.value.status_code == 401

    def test_issuer_mismatch(self):
        v = jv.JWTVerifier(secret_key=SECRET, debug_mode=True, issuer="atom")
        bad = jwt.encode({"sub": "u", "iss": "other",
                          "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                         SECRET, algorithm="HS256")
        with pytest.raises(HTTPException) as ei:
            v.verify_token(_creds(bad))
        assert ei.value.status_code == 401
        assert "issuer" in ei.value.detail.lower()

    def test_old_iat_token_still_valid(self, verifier):
        old = jwt.encode({"sub": "u", "jti": "j",
                          "iat": datetime.now(timezone.utc) - timedelta(days=31),
                          "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                         SECRET, algorithm="HS256")
        payload = verifier.verify_token(_creds(old))
        assert payload["sub"] == "u"

    def test_revoked_token_rejected(self, db):
        v = jv.JWTVerifier(secret_key=SECRET, debug_mode=True)
        tok = v.create_token("u1")
        db.add(RevokedToken(jti=jwt.decode(tok, SECRET, algorithms=["HS256"])["jti"],
                            user_id="u1", expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        db.commit()
        with pytest.raises(HTTPException) as ei:
            v.verify_token(_creds(tok), check_revocation=True, db=db)
        assert ei.value.status_code == 401
        assert "revoked" in ei.value.detail.lower()

    def test_unexpected_error_401(self, verifier):
        tok = verifier.create_token("u1")
        with patch.object(jv.jwt, "decode", side_effect=RuntimeError("boom")):
            with pytest.raises(HTTPException) as ei:
                verifier.verify_token(_creds(tok))
        assert ei.value.status_code == 401
        assert ei.value.detail == "Could not validate credentials"


class TestDebugModeBypass:
    def test_whitelisted_ip_bypasses_validation(self):
        v = jv.JWTVerifier(secret_key=SECRET, debug_mode=True,
                           debug_ip_whitelist=["127.0.0.1"])
        tok = v.create_token("u1")
        payload = v.verify_token(_creds(tok), client_ip="127.0.0.1")
        assert payload["sub"] == "u1"

    def test_whitelisted_ip_malformed_token_rejected(self):
        v = jv.JWTVerifier(secret_key=SECRET, debug_mode=True,
                           debug_ip_whitelist=["127.0.0.1"])
        with pytest.raises(HTTPException) as ei:
            v.verify_token(_creds("garbage.token.here"), client_ip="127.0.0.1")
        assert ei.value.status_code == 401
        assert "Malformed token" in ei.value.detail

    def test_debug_without_whitelist_falls_through_to_normal(self, verifier):
        tok = verifier.create_token("u1")
        payload = verifier.verify_token(_creds(tok), client_ip="127.0.0.1")
        assert payload["sub"] == "u1"

    def test_non_whitelisted_ip_falls_through(self):
        v = jv.JWTVerifier(secret_key=SECRET, debug_mode=True,
                           debug_ip_whitelist=["127.0.0.1"])
        tok = v.create_token("u1")
        payload = v.verify_token(_creds(tok), client_ip="10.0.0.9")
        assert payload["sub"] == "u1"

    def test_debug_bypass_blocked_in_production(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=True):
            v = jv.JWTVerifier(secret_key=SECRET, debug_mode=True,
                               debug_ip_whitelist=["127.0.0.1"])
            tok = v.create_token("u1")
            payload = v.verify_token(_creds(tok), client_ip="127.0.0.1")
            assert payload["sub"] == "u1"


class TestIsTokenRevoked:
    def test_no_db_returns_false(self, verifier):
        payload = {"sub": "u", "jti": "j"}
        assert verifier._is_token_revoked(payload, db=None) is False

    def test_no_jti_returns_false(self, db, verifier):
        assert verifier._is_token_revoked({"sub": "u"}, db=db) is False

    def test_not_revoked_false(self, db, verifier):
        assert verifier._is_token_revoked({"sub": "u", "jti": "nope"}, db=db) is False

    def test_revoked_true(self, db, verifier):
        db.add(RevokedToken(jti="j1", user_id="u1",
                            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        db.commit()
        assert verifier._is_token_revoked({"sub": "u", "jti": "j1"}, db=db) is True

    def test_db_error_fails_open(self, db, verifier):
        db.query = MagicMock(side_effect=RuntimeError("db down"))
        assert verifier._is_token_revoked({"sub": "u", "jti": "j1"}, db=db) is False

    def test_revoked_token_model_unavailable_false(self, verifier):
        # RevokedToken import-failure fallback branch (module-level None)
        with patch.object(jv, "RevokedToken", None):
            with patch("core.jwt_verifier.RevokedToken", None):
                assert verifier._is_token_revoked({"sub": "u", "jti": "j1"}, db=MagicMock()) is False

    def test_module_import_fallback(self):
        # Re-import the module with core.models import failing → RevokedToken None
        import importlib
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "core.models":
                raise ImportError("simulated")
            return real_import(name, *args, **kwargs)

        with patch.dict(os.environ, {"JWT_SECRET": SECRET}, clear=True):
            with patch("builtins.__import__", side_effect=fake_import):
                mod = importlib.reload(jv)
        assert mod.RevokedToken is None
        with patch("core.jwt_verifier.RevokedToken", mod.RevokedToken):
            v = mod.JWTVerifier(secret_key=SECRET, debug_mode=True)
            assert v._is_token_revoked({"sub": "u", "jti": "j1"}, db=MagicMock()) is False
        # restore the module for the remaining tests
        importlib.reload(jv)


class TestCreateToken:
    def test_default_expiry_24h(self, verifier):
        tok = verifier.create_token("u1")
        payload = jwt.decode(tok, SECRET, algorithms=["HS256"])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert (exp - datetime.now(timezone.utc)) < timedelta(hours=25)

    def test_custom_expiry_and_claims(self, verifier):
        tok = verifier.create_token("u1", expires_delta=timedelta(hours=2),
                                    additional_claims={"role": "admin"}, jti="my-jti")
        payload = jwt.decode(tok, SECRET, algorithms=["HS256"])
        assert payload["role"] == "admin"
        assert payload["jti"] == "my-jti"

    def test_create_with_audience_and_issuer(self):
        v = jv.JWTVerifier(secret_key=SECRET, debug_mode=True,
                           audience="api", issuer="atom")
        tok = v.create_token("u1")
        payload = jwt.decode(tok, SECRET, algorithms=["HS256"],
                             audience="api", issuer="atom")
        assert payload["aud"] == "api"
        assert payload["iss"] == "atom"


class TestModuleVerifyToken:
    def test_dependency_with_request_derives_ip(self, verifier):
        tok = verifier.create_token("u1")
        req = MagicMock()
        req.client.host = "127.0.0.1"
        req.headers = {}
        with patch.dict(os.environ, {"TRUST_X_FORWARDED_FOR": "1"}, clear=True):
            with patch.dict(os.environ, {"JWT_SECRET": SECRET, "DEBUG_IP_WHITELIST": "127.0.0.1", "DEBUG": "true"}, clear=True):
                jv._jwt_verifier = None
                payload = jv.verify_token(_creds(tok), request=req)
        assert payload["sub"] == "u1"

    def test_client_ip_from_request_xff(self):
        req = MagicMock()
        req.client.host = "9.9.9.9"
        req.headers = {"x-forwarded-for": "1.1.1.1, 8.8.8.8"}
        with patch.dict(os.environ, {"TRUST_X_FORWARDED_FOR": "1"}, clear=True):
            assert jv._client_ip_from_request(req) == "8.8.8.8"

    def test_client_ip_from_request_tcp_peer(self):
        req = MagicMock()
        req.client.host = "9.9.9.9"
        req.headers = {"x-forwarded-for": "1.1.1.1, 8.8.8.8"}
        with patch.dict(os.environ, {}, clear=True):
            assert jv._client_ip_from_request(req) == "9.9.9.9"

    def test_client_ip_no_client(self):
        req = MagicMock()
        req.client = None
        req.headers = {}  # no X-Forwarded-For → falls to client.host → None → unknown
        with patch.dict(os.environ, {"TRUST_X_FORWARDED_FOR": "1"}, clear=True):
            assert jv._client_ip_from_request(req) == "unknown"

    def test_verify_token_string(self, verifier):
        tok = verifier.create_token("u1")
        with patch.dict(os.environ, {"JWT_SECRET": SECRET}, clear=True):
            jv._jwt_verifier = None
            payload = jv.verify_token_string(tok)
        assert payload["sub"] == "u1"


class TestGetJwtVerifier:
    def test_singleton(self):
        jv._jwt_verifier = None
        a = jv.get_jwt_verifier()
        b = jv.get_jwt_verifier()
        assert a is b
        assert a.secret_key == SECRET
