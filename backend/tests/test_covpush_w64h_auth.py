"""
Coverage wave 64h — core/auth.py (standalone, function-level, TDD).

Full contract coverage of the auth utility module:
- verify_password / get_password_hash (bcrypt boundary, type guards, error paths)
- create_access_token (default + custom expiry, jti)
- in-memory token revocation (revoke/check/prune)
- get_current_user (cookie fallbacks, claim conventions, revocation, status gate)
- get_current_tenant (resolve, fallback, 404)
- get_current_user_ws / decode_token / verify_mobile_token (all branches)
- verify_biometric_signature (EC success, RSA fallback, failures)
- create_mobile_token / get_mobile_device / authenticate_mobile_user
- generate_satellite_key
- import-time SECRET_KEY branches (dev auto-generate / production fail-closed)
  via in-process importlib.reload with restored module state.

No network, no real DB writes, no LLM spend — everything is mocked (MagicMock
db sessions) or local crypto. The module's in-memory revoke list and
SECRET_KEY are patched per-test and restored.
"""

import asyncio
import base64
import importlib
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from jose import JWTError, jwt

import core.auth as auth_mod

_ORIG_AUTH_BINDINGS = {_n: getattr(auth_mod, _n) for _n in dir(auth_mod)}


def _reload_auth():
    """Reload core.auth, then restore the original module-level bindings.

    `importlib.reload` re-executes the module and rebinds every function
    object, so sibling suites that did `from core.auth import get_current_user`
    at collection time hold stale references — their
    `app.dependency_overrides[get_current_user]` then misses the route's
    `Depends()` key and the real auth dependency runs (401s). Re-binding the
    pre-reload objects keeps every imported reference valid.
    """
    importlib.reload(auth_mod)
    for _n, _o in _ORIG_AUTH_BINDINGS.items():
        if hasattr(auth_mod, _n):
            setattr(auth_mod, _n, _o)


@pytest.fixture(autouse=True)
def _stable_auth_module(monkeypatch):
    """Pin SECRET_KEY/ALGORITHM and clear the in-memory revoke lists so tests
    are deterministic; restore everything afterwards (sibling-suite safety)."""
    original_key = auth_mod.SECRET_KEY
    original_algo = auth_mod.ALGORITHM
    original_revoked = set(auth_mod._revoked_tokens)
    original_expiry = dict(auth_mod._revoked_expiry)
    auth_mod._revoked_tokens.clear()
    auth_mod._revoked_expiry.clear()

    monkeypatch.setattr(auth_mod, "SECRET_KEY", "covpush-w64h-stable-secret")
    yield auth_mod

    auth_mod.SECRET_KEY = original_key
    auth_mod.ALGORITHM = original_algo
    auth_mod._revoked_tokens.clear()
    auth_mod._revoked_tokens.update(original_revoked)
    auth_mod._revoked_expiry.clear()
    auth_mod._revoked_expiry.update(original_expiry)


def _make_user(status="active", uid="u-1", email="u@x", role="member"):
    u = MagicMock()
    u.id = uid
    u.email = email
    u.first_name = "A"
    u.last_name = "B"
    u.role = role
    u.status = status
    u.hashed_password = "hashed"
    return u


def _make_token(am, sub="u-1", **extra):
    payload = {"sub": sub, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    payload.update(extra)
    return jwt.encode(payload, am.SECRET_KEY, algorithm=am.ALGORITHM)


def _db_with_user(user):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    return db


# ===========================================================================
# verify_password — all branches
# ===========================================================================


class TestVerifyPassword:
    def test_valid_string_pair(self):
        am = auth_mod
        h = am.get_password_hash("s3cret")
        assert am.verify_password("s3cret", h) is True

    def test_wrong_password(self):
        am = auth_mod
        h = am.get_password_hash("right")
        assert am.verify_password("wrong", h) is False

    def test_bytes_plain_password(self):
        am = auth_mod
        h = am.get_password_hash("s3cret")
        assert am.verify_password(b"s3cret", h) is True

    def test_bytes_hashed_password(self):
        am = auth_mod
        h = am.get_password_hash("s3cret").encode("utf-8")
        assert am.verify_password("s3cret", h) is True

    def test_72_byte_boundary(self):
        """The hard bcrypt limit is 72 bytes; a 72-byte password must verify
        against its own hash (regression for the 71-byte truncation bug)."""
        am = auth_mod
        pw = "a" * 72
        h = am.get_password_hash(pw)
        assert am.verify_password(pw, h) is True

    def test_longer_password_prefix_still_verifies(self):
        """verify_password truncates the input to 72 bytes, so a 72-byte
        prefix of a longer password verifies (documented bcrypt behavior)."""
        am = auth_mod
        h = am.get_password_hash("a" * 72)
        assert am.verify_password("a" * 80, h) is True

    def test_non_string_plain_password_false(self):
        assert auth_mod.verify_password(None, "whatever") is False
        assert auth_mod.verify_password(12345, "whatever") is False

    def test_non_string_hash_false(self):
        assert auth_mod.verify_password("pw", None) is False
        assert auth_mod.verify_password("pw", 42) is False

    def test_invalid_hash_value_error_false(self):
        assert auth_mod.verify_password("pw", "$2b$12$not-a-valid-bcrypt-hash") is False

    def test_generic_exception_false(self):
        am = auth_mod
        h = am.get_password_hash("pw")
        with patch.object(am.bcrypt, "checkpw", side_effect=RuntimeError("boom")):
            assert am.verify_password("pw", h) is False


# ===========================================================================
# get_password_hash — all branches
# ===========================================================================


class TestGetPasswordHash:
    def test_str_input_roundtrip(self):
        am = auth_mod
        h = am.get_password_hash("pw")
        assert h.startswith("$2")
        assert am.verify_password("pw", h) is True

    def test_bytes_input_roundtrip(self):
        am = auth_mod
        h = am.get_password_hash(b"byte-pw")
        assert am.verify_password("byte-pw", h) is True

    def test_over_72_bytes_rejected(self):
        with pytest.raises(ValueError, match="72-byte"):
            auth_mod.get_password_hash("x" * 73)

    def test_exactly_72_bytes_accepted(self):
        am = auth_mod
        h = am.get_password_hash("x" * 72)
        assert am.verify_password("x" * 72, h) is True

    def test_unique_salts(self):
        am = auth_mod
        assert am.get_password_hash("pw") != am.get_password_hash("pw")


# ===========================================================================
# create_access_token — both expiry paths + jti
# ===========================================================================


class TestCreateAccessToken:
    def test_default_expiry(self):
        am = auth_mod
        tok = am.create_access_token({"sub": "u1"})
        payload = jwt.decode(tok, am.SECRET_KEY, algorithms=[am.ALGORITHM])
        assert payload["sub"] == "u1"
        assert "jti" in payload
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert timedelta(hours=23, minutes=50) < (exp - datetime.now(timezone.utc)) < timedelta(hours=24, minutes=10)

    def test_custom_expiry(self):
        am = auth_mod
        tok = am.create_access_token({"sub": "u1"}, expires_delta=timedelta(minutes=5))
        payload = jwt.decode(tok, am.SECRET_KEY, algorithms=[am.ALGORITHM])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert timedelta(minutes=4) < (exp - datetime.now(timezone.utc)) < timedelta(minutes=6)

    def test_unique_jti_per_token(self):
        am = auth_mod
        t1 = jwt.decode(am.create_access_token({"sub": "u1"}), am.SECRET_KEY, algorithms=[am.ALGORITHM])["jti"]
        t2 = jwt.decode(am.create_access_token({"sub": "u1"}), am.SECRET_KEY, algorithms=[am.ALGORITHM])["jti"]
        assert t1 != t2

    def test_payload_copied_not_mutated(self):
        am = auth_mod
        data = {"sub": "u1"}
        tok = am.create_access_token(data)
        assert data == {"sub": "u1"}
        assert "jti" not in data


# ===========================================================================
# In-memory revocation list
# ===========================================================================


class TestRevocation:
    def test_revoke_and_check(self):
        am = auth_mod
        exp = int(datetime.now(timezone.utc).timestamp()) + 1000
        am.revoke_token("jti-A", exp)
        assert am.is_token_revoked("jti-A") is True
        assert "jti-A" in am._revoked_expiry

    def test_unknown_jti(self):
        assert auth_mod.is_token_revoked("missing-jti") is False

    def test_none_and_empty_jti(self):
        assert auth_mod.is_token_revoked(None) is False
        assert auth_mod.is_token_revoked("") is False

    def test_expired_revocation_pruned(self):
        am = auth_mod
        past = int(datetime.now(timezone.utc).timestamp()) - 100
        am.revoke_token("stale-jti", past)
        assert am.is_token_revoked("stale-jti") is False
        assert "stale-jti" not in am._revoked_tokens
        assert "stale-jti" not in am._revoked_expiry

    def test_pruning_spares_active_entries(self):
        am = auth_mod
        now = datetime.now(timezone.utc).timestamp()
        am.revoke_token("live-jti", int(now) + 1000)
        am.revoke_token("dead-jti", int(now) - 1000)
        assert am.is_token_revoked("live-jti") is True
        assert "live-jti" in am._revoked_expiry
        assert "dead-jti" not in am._revoked_expiry


# ===========================================================================
# get_current_user — every branch
# ===========================================================================


class TestGetCurrentUser:
    def _run(self, am, request=None, token=None, db=None):
        return asyncio.run(am.get_current_user(
            request=request or MagicMock(cookies={}), token=token, db=db or MagicMock()
        ))

    def test_valid_bearer(self):
        am = auth_mod
        user = _make_user()
        assert self._run(am, token=_make_token(am), db=_db_with_user(user)) is user

    def test_quoted_token_unwrapped(self):
        am = auth_mod
        user = _make_user()
        tok = '"%s"' % _make_token(am)
        assert self._run(am, token=tok, db=_db_with_user(user)) is user

    def test_cookie_fallback(self):
        am = auth_mod
        user = _make_user()
        req = MagicMock(cookies={"next-auth.session-token": _make_token(am)})
        assert self._run(am, request=req, token=None, db=_db_with_user(user)) is user

    def test_secure_cookie_fallback(self):
        am = auth_mod
        user = _make_user()
        req = MagicMock(cookies={"__Secure-next-auth.session-token": _make_token(am)})
        assert self._run(am, request=req, token=None, db=_db_with_user(user)) is user

    def test_plain_cookie_missing_then_secure_checked(self):
        """Only the plain cookie exists with a bad value; the secure cookie is
        consulted next and raises (no token found)."""
        am = auth_mod
        req = MagicMock(cookies={"next-auth.session-token": "garbage"})
        with pytest.raises(HTTPException) as exc:
            self._run(am, request=req, token=None, db=MagicMock())
        assert exc.value.status_code == 401

    def test_no_token_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            self._run(auth_mod, token=None, db=MagicMock())
        assert exc.value.status_code == 401

    def test_bad_format_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            self._run(auth_mod, token="not-a-jwt", db=MagicMock())
        assert exc.value.status_code == 401

    def test_invalid_signature_raises_401(self):
        am = auth_mod
        bad = jwt.encode({"sub": "u1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "WRONG", algorithm="HS256")
        with pytest.raises(HTTPException) as exc:
            self._run(am, token=bad, db=MagicMock())
        assert exc.value.status_code == 401

    def test_jwt_error_branch(self):
        am = auth_mod
        tok = _make_token(am)
        with patch.object(am.jwt, "decode", side_effect=JWTError("bad")):
            with pytest.raises(HTTPException) as exc:
                self._run(am, token=tok, db=MagicMock())
        assert exc.value.status_code == 401

    def test_generic_decode_exception_raises_401(self):
        am = auth_mod
        tok = _make_token(am)
        with patch.object(am.jwt, "decode", side_effect=RuntimeError("boom")):
            with pytest.raises(HTTPException) as exc:
                self._run(am, token=tok, db=MagicMock())
        assert exc.value.status_code == 401

    def test_missing_all_claims_raises_401(self):
        am = auth_mod
        tok = jwt.encode({"exp": datetime.now(timezone.utc) + timedelta(hours=1)}, am.SECRET_KEY, algorithm=am.ALGORITHM)
        with pytest.raises(HTTPException) as exc:
            self._run(am, token=tok, db=MagicMock())
        assert exc.value.status_code == 401

    def test_id_claim_fallback(self):
        am = auth_mod
        user = _make_user()
        tok = jwt.encode({"id": user.id, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, am.SECRET_KEY, algorithm=am.ALGORITHM)
        assert self._run(am, token=tok, db=_db_with_user(user)) is user

    def test_user_id_claim_fallback(self):
        am = auth_mod
        user = _make_user()
        tok = jwt.encode({"user_id": user.id, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, am.SECRET_KEY, algorithm=am.ALGORITHM)
        assert self._run(am, token=tok, db=_db_with_user(user)) is user

    def test_revoked_token_raises_401(self):
        am = auth_mod
        tok = _make_token(am, jti="gc-revoked")
        am.revoke_token("gc-revoked", int(datetime.now(timezone.utc).timestamp()) + 1000)
        with pytest.raises(HTTPException) as exc:
            self._run(am, token=tok, db=_db_with_user(_make_user()))
        assert exc.value.status_code == 401

    def test_user_not_found_raises_401(self):
        am = auth_mod
        with pytest.raises(HTTPException) as exc:
            self._run(am, token=_make_token(am), db=_db_with_user(None))
        assert exc.value.status_code == 401

    def test_non_active_user_raises_401(self):
        am = auth_mod
        user = _make_user(status="suspended")
        with pytest.raises(HTTPException) as exc:
            self._run(am, token=_make_token(am), db=_db_with_user(user))
        assert exc.value.status_code == 401


# ===========================================================================
# get_current_tenant
# ===========================================================================


class TestGetCurrentTenant:
    def _run(self, am, user, db):
        return asyncio.run(am.get_current_tenant(current_user=user, db=db))

    def test_tenant_found_by_id(self):
        am = auth_mod
        tenant = MagicMock(id="t-1")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = tenant
        with patch("core.personal_scope.resolve_tenant_id", return_value="t-1"):
            assert self._run(am, _make_user(), db) is tenant

    def test_falls_back_to_first_tenant(self):
        am = auth_mod
        tenant = MagicMock(id="default")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.first.return_value = tenant
        with patch("core.personal_scope.resolve_tenant_id", return_value="missing"):
            assert self._run(am, _make_user(), db) is tenant

    def test_no_tenant_raises_404(self):
        am = auth_mod
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.first.return_value = None
        with patch("core.personal_scope.resolve_tenant_id", return_value="missing"):
            with pytest.raises(HTTPException) as exc:
                self._run(am, _make_user(), db)
        assert exc.value.status_code == 404


# ===========================================================================
# get_current_user_ws
# ===========================================================================


class TestGetCurrentUserWs:
    def _run(self, am, token, db):
        return asyncio.run(am.get_current_user_ws(token, db))

    def test_valid(self):
        am = auth_mod
        user = _make_user()
        assert self._run(am, _make_token(am), _db_with_user(user)) is user

    def test_empty_token(self):
        assert self._run(auth_mod, "", MagicMock()) is None

    def test_bad_format(self):
        assert self._run(auth_mod, "no-dots", MagicMock()) is None

    def test_missing_sub(self):
        am = auth_mod
        tok = jwt.encode({"exp": datetime.now(timezone.utc) + timedelta(hours=1)}, am.SECRET_KEY, algorithm=am.ALGORITHM)
        assert self._run(am, tok, MagicMock()) is None

    def test_id_claim_accepted(self):
        am = auth_mod
        user = _make_user()
        tok = jwt.encode({"id": user.id, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, am.SECRET_KEY, algorithm=am.ALGORITHM)
        assert self._run(am, tok, _db_with_user(user)) is user

    def test_revoked(self):
        am = auth_mod
        tok = _make_token(am, jti="ws-revoked")
        am.revoke_token("ws-revoked", int(datetime.now(timezone.utc).timestamp()) + 1000)
        assert self._run(am, tok, _db_with_user(_make_user())) is None

    def test_user_not_found(self):
        am = auth_mod
        assert self._run(am, _make_token(am), _db_with_user(None)) is None

    def test_non_active_user(self):
        am = auth_mod
        assert self._run(am, _make_token(am), _db_with_user(_make_user(status="deleted"))) is None

    def test_jwt_error(self):
        am = auth_mod
        bad = jwt.encode({"sub": "u1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "WRONG", algorithm="HS256")
        assert self._run(am, bad, MagicMock()) is None

    def test_user_id_claim_accepted(self):
        am = auth_mod
        user = _make_user()
        tok = jwt.encode({"user_id": user.id, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, am.SECRET_KEY, algorithm=am.ALGORITHM)
        assert self._run(am, tok, _db_with_user(user)) is user


# ===========================================================================
# decode_token
# ===========================================================================


class TestDecodeToken:
    def test_valid(self):
        am = auth_mod
        tok = _make_token(am)
        assert am.decode_token(tok)["sub"] == "u-1"

    def test_none_and_empty(self):
        assert auth_mod.decode_token(None) is None
        assert auth_mod.decode_token("") is None

    def test_bad_format(self):
        assert auth_mod.decode_token("no-dots") is None

    def test_invalid_signature(self):
        am = auth_mod
        bad = jwt.encode({"sub": "u1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "WRONG", algorithm="HS256")
        assert am.decode_token(bad) is None

    def test_jwt_error_branch(self):
        am = auth_mod
        with patch.object(am.jwt, "decode", side_effect=JWTError("bad")):
            assert am.decode_token(_make_token(am)) is None

    def test_generic_exception_branch(self):
        am = auth_mod
        with patch.object(am.jwt, "decode", side_effect=RuntimeError("boom")):
            assert am.decode_token(_make_token(am)) is None

    def test_revoked(self):
        am = auth_mod
        tok = _make_token(am, jti="dec-revoked")
        am.revoke_token("dec-revoked", int(datetime.now(timezone.utc).timestamp()) + 1000)
        assert am.decode_token(tok) is None

    def test_expired(self):
        am = auth_mod
        tok = jwt.encode({"sub": "u1", "exp": datetime.now(timezone.utc) - timedelta(hours=1)}, am.SECRET_KEY, algorithm=am.ALGORITHM)
        assert am.decode_token(tok) is None


# ===========================================================================
# generate_satellite_key
# ===========================================================================


class TestSatelliteKey:
    def test_format(self):
        k1 = auth_mod.generate_satellite_key()
        k2 = auth_mod.generate_satellite_key()
        assert k1.startswith("sk-") and k2.startswith("sk-")
        assert len(k1) == len("sk-") + 48
        assert k1 != k2


# ===========================================================================
# verify_mobile_token
# ===========================================================================


class TestVerifyMobileToken:
    def test_valid(self):
        am = auth_mod
        user = _make_user()
        assert am.verify_mobile_token(_make_token(am), _db_with_user(user)) is user

    def test_missing_sub(self):
        am = auth_mod
        tok = jwt.encode({"exp": datetime.now(timezone.utc) + timedelta(hours=1)}, am.SECRET_KEY, algorithm=am.ALGORITHM)
        assert am.verify_mobile_token(tok, MagicMock()) is None

    def test_user_not_found(self):
        am = auth_mod
        assert am.verify_mobile_token(_make_token(am), _db_with_user(None)) is None

    def test_non_active_user(self):
        am = auth_mod
        assert am.verify_mobile_token(_make_token(am), _db_with_user(_make_user(status="deleted"))) is None

    def test_jwt_error(self):
        am = auth_mod
        bad = jwt.encode({"sub": "u1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "WRONG", algorithm="HS256")
        assert am.verify_mobile_token(bad, MagicMock()) is None


# ===========================================================================
# verify_biometric_signature — EC success, RSA fallback, failures
# ===========================================================================


class TestVerifyBiometricSignature:
    @pytest.fixture(scope="class")
    def ec_keypair(self):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

        key = ec.generate_private_key(ec.SECP256R1())
        pub_pem = key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()

        def sign(challenge: str) -> str:
            sig = key.sign(challenge.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
            return base64.b64encode(sig).decode()

        return pub_pem, sign

    @pytest.fixture(scope="class")
    def rsa_keypair(self):
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub_pem = key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()

        def sign(challenge: str) -> str:
            sig = key.sign(
                challenge.encode("utf-8"),
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256(),
            )
            return base64.b64encode(sig).decode()

        return pub_pem, sign

    def test_valid_ec_signature(self, ec_keypair):
        pub, sign = ec_keypair
        assert auth_mod.verify_biometric_signature(sign("challenge"), pub, "challenge") is True

    def test_wrong_challenge_ec(self, ec_keypair):
        pub, sign = ec_keypair
        assert auth_mod.verify_biometric_signature(sign("real"), pub, "forged") is False

    def test_ec_verification_failure_uses_rsa_fallback(self, rsa_keypair):
        """An RSA signature fails EC verification, then succeeds via the RSA
        PSS fallback path (covers the fallback branch end-to-end)."""
        pub, sign = rsa_keypair
        assert auth_mod.verify_biometric_signature(sign("challenge"), pub, "challenge") is True

    def test_invalid_base64(self):
        assert auth_mod.verify_biometric_signature("!!not-base64!!", "pub", "challenge") is False

    def test_invalid_public_key(self):
        assert auth_mod.verify_biometric_signature("c2ln", "not-a-key", "challenge") is False

    def test_none_inputs(self):
        assert auth_mod.verify_biometric_signature(None, "pub", "challenge") is False


# ===========================================================================
# create_mobile_token
# ===========================================================================


class TestCreateMobileToken:
    def test_default_expiry(self):
        am = auth_mod
        user = _make_user()
        tokens = am.create_mobile_token(user, "dev-1")
        assert tokens["token_type"] == "bearer"
        access = jwt.decode(tokens["access_token"], am.SECRET_KEY, algorithms=[am.ALGORITHM])
        refresh = jwt.decode(tokens["refresh_token"], am.SECRET_KEY, algorithms=[am.ALGORITHM])
        assert access["sub"] == str(user.id)
        assert access["email"] == "u@x"
        assert access["device_id"] == "dev-1"
        assert access["platform"] == "mobile"
        assert refresh["type"] == "refresh"
        assert refresh["exp"] > access["exp"]
        # The exp claim is an int epoch (no microseconds); expires_at keeps them,
        # so compare at second precision.
        expires_at = datetime.fromisoformat(tokens["expires_at"].replace("Z", "+00:00"))
        assert expires_at.replace(microsecond=0) == datetime.fromtimestamp(access["exp"], tz=timezone.utc).replace(microsecond=0)

    def test_custom_expiry(self):
        am = auth_mod
        tokens = am.create_mobile_token(_make_user(), "dev-2", expires_delta=timedelta(hours=1))
        access = jwt.decode(tokens["access_token"], am.SECRET_KEY, algorithms=[am.ALGORITHM])
        exp = datetime.fromtimestamp(access["exp"], tz=timezone.utc)
        assert timedelta(minutes=55) < (exp - datetime.now(timezone.utc)) < timedelta(hours=1, minutes=5)


# ===========================================================================
# get_mobile_device
# ===========================================================================


class TestGetMobileDevice:
    def test_active_device(self):
        am = auth_mod
        dev = MagicMock(status="active")
        assert am.get_mobile_device("d1", "u1", _db_with_user(dev)) is dev

    def test_inactive_device(self):
        am = auth_mod
        dev = MagicMock(status="revoked")
        assert am.get_mobile_device("d1", "u1", _db_with_user(dev)) is None

    def test_no_device(self):
        am = auth_mod
        assert am.get_mobile_device("d1", "u1", _db_with_user(None)) is None


# ===========================================================================
# authenticate_mobile_user — every branch
# ===========================================================================


class TestAuthenticateMobileUser:
    def _run(self, am, **kw):
        return asyncio.run(am.authenticate_mobile_user(**kw))

    def _db_user_then_device(self, user, device):
        db = MagicMock()
        user_q = MagicMock()
        user_q.filter.return_value.first.return_value = user
        dev_q = MagicMock()
        dev_q.filter.return_value.first.return_value = device
        db.query.side_effect = [user_q, dev_q]
        return db

    def test_success_new_device(self):
        am = auth_mod
        user = _make_user()
        user.hashed_password = am.get_password_hash("ValidPass123!")
        db = self._db_user_then_device(user, None)
        result = self._run(am, email="u@x", password="ValidPass123!", device_token="dt1", platform="ios", db=db)
        assert result is not None
        assert result["user"]["id"] == str(user.id)
        assert result["user"]["email"] == "u@x"
        assert result["user"]["role"] == "member"
        assert result["access_token"]
        assert result["refresh_token"]
        db.add.assert_called_once()
        db.commit.assert_called()
        db.refresh.assert_called_once()
        created = db.add.call_args[0][0]
        assert created.platform == "ios"
        assert created.status == "active"

    def test_existing_device_updated(self):
        am = auth_mod
        user = _make_user()
        user.hashed_password = am.get_password_hash("ValidPass123!")
        existing = MagicMock(id="dev-exist", status="inactive", platform="android")
        db = self._db_user_then_device(user, existing)
        result = self._run(am, email="u@x", password="ValidPass123!", device_token="dt1", platform="ios", db=db)
        assert result is not None
        assert existing.platform == "ios"
        assert existing.status == "active"
        assert existing.last_active is not None
        db.add.assert_not_called()
        db.commit.assert_called()

    def test_unknown_user(self):
        am = auth_mod
        assert self._run(am, email="no@x", password="p", device_token="dt", platform="ios", db=_db_with_user(None)) is None

    def test_non_active_user(self):
        am = auth_mod
        assert self._run(am, email="u@x", password="p", device_token="dt", platform="ios",
                         db=_db_with_user(_make_user(status="suspended"))) is None

    def test_wrong_password(self):
        am = auth_mod
        user = _make_user()
        user.hashed_password = am.get_password_hash("CorrectPass123!")
        assert self._run(am, email="u@x", password="WrongPass123!", device_token="dt", platform="ios",
                         db=_db_with_user(user)) is None


# ===========================================================================
# Import-time SECRET_KEY branches (dev auto-generate / production fail-closed)
# ===========================================================================


class TestModuleImportTimeSecretKey:
    """In-process reloads to execute the import-time SECRET_KEY resolution
    branches (lines 26-33). Each test restores the module state afterwards by
    reloading with the original environment, so sibling suites are unaffected."""

    def _capture_env(self):
        return {
            k: os.environ.get(k)
            for k in ("SECRET_KEY", "JWT_SECRET", "ENVIRONMENT", "NODE_ENV")
        }

    def _restore_env(self, saved):
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_dev_environment_auto_generates_secret(self):
        saved = self._capture_env()
        try:
            os.environ.pop("SECRET_KEY", None)
            os.environ.pop("JWT_SECRET", None)
            os.environ.pop("NODE_ENV", None)
            os.environ["ENVIRONMENT"] = "development"
            _reload_auth()
            assert auth_mod.SECRET_KEY is not None
            assert auth_mod.SECRET_KEY != "covpush-w64h-stable-secret"
        finally:
            self._restore_env(saved)
            _reload_auth()

    def test_production_without_secret_fails_closed(self):
        saved = self._capture_env()
        try:
            os.environ.pop("SECRET_KEY", None)
            os.environ.pop("JWT_SECRET", None)
            os.environ.pop("NODE_ENV", None)
            os.environ["ENVIRONMENT"] = "production"
            with pytest.raises(ValueError, match="SECRET_KEY"):
                _reload_auth()
        finally:
            self._restore_env(saved)
            _reload_auth()

    def test_production_via_node_env_fails_closed(self):
        saved = self._capture_env()
        try:
            os.environ.pop("SECRET_KEY", None)
            os.environ.pop("JWT_SECRET", None)
            os.environ.pop("ENVIRONMENT", None)
            os.environ["NODE_ENV"] = "production"
            with pytest.raises(ValueError, match="SECRET_KEY"):
                _reload_auth()
        finally:
            self._restore_env(saved)
            _reload_auth()
