"""
Coverage + security bug-hunt tests for core/auth.py and core/auth_helpers.py.

These modules have partial existing coverage from:
- tests/unit/security/test_jwt_validation.py (token gen/decode happy paths)
- tests/unit/security/test_auth_helpers.py (helpers + DB-backed revocation)
- tests/test_auth_fixes.py (JWT claim-name fallback)
- tests/test_ws_token_revocation.py (WS revoke)

This file fills the gaps: get_current_user (all branches), get_current_tenant,
get_current_user_ws, decode_token edges, mobile auth (verify_mobile_token,
authenticate_mobile_user, get_mobile_device, create_mobile_token),
verify_biometric_signature, generate_satellite_key, and the in-memory
revocation list. Plus the auth_helpers emergency-bypass and error branches.

Bug-hunt (TDD) finding documented inline:
- verify_mobile_token returns a SUSPENDED/DELETED user as valid — it skips the
  status check that every other auth path (get_current_user,
  get_current_user_ws, authenticate_mobile_user) enforces, so a revoked user's
  existing mobile JWT keeps authenticating them.
"""

import asyncio
import base64
import importlib
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from jose import jwt

sys.path.insert(0, "/Users/rushiparikh/projects/atom/backend")


# Use a known SECRET_KEY for deterministic token signing. core.auth reads
# SECRET_KEY at import time, so we patch the module attribute in place (NOT
# importlib.reload — reloading mutates global state for the whole session and
# breaks other test files that imported SECRET_KEY at their top level).
@pytest.fixture(autouse=True)
def _stable_auth_module(monkeypatch):
    import core.auth as auth_mod
    original_key = auth_mod.SECRET_KEY
    original_algo = auth_mod.ALGORITHM
    # Clear the in-memory revoke list so tests start clean.
    original_revoked = set(auth_mod._revoked_tokens)
    original_expiry = dict(auth_mod._revoked_expiry)
    auth_mod._revoked_tokens.clear()
    auth_mod._revoked_expiry.clear()

    auth_mod.SECRET_KEY = "stable-secret-for-auth-coverage-tests"
    yield auth_mod

    # Restore everything so sibling test files see the original module state.
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


def _make_token(auth_mod, sub="u-1", **extra):
    payload = {"sub": sub, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    payload.update(extra)
    return jwt.encode(payload, auth_mod.SECRET_KEY, algorithm=auth_mod.ALGORITHM)


# ===========================================================================
# core/auth.py — verify_password / get_password_hash edge cases
# ===========================================================================


class TestPasswordHashingEdges:
    def test_verify_password_bytes_input(self, _stable_auth_module):
        am = _stable_auth_module
        h = am.get_password_hash("secret")
        assert am.verify_password(b"secret", h) is True

    def test_verify_password_bytes_hash(self, _stable_auth_module):
        am = _stable_auth_module
        h = am.get_password_hash("secret").encode()
        assert am.verify_password("secret", h) is True

    def test_verify_password_truncates_to_71_bytes(self, _stable_auth_module):
        """verify_password truncates to 71 bytes; a 71-byte prefix verifies
        against a hash of a longer string (bcrypt 72-byte limit)."""
        am = _stable_auth_module
        long_pw = "a" * 71
        h = am.get_password_hash(long_pw)
        assert am.verify_password(long_pw, h) is True

    def test_verify_password_invalid_hash_returns_false(self, _stable_auth_module):
        am = _stable_auth_module
        assert am.verify_password("secret", "not-a-valid-hash") is False

    def test_verify_password_none_password_returns_false(self, _stable_auth_module):
        am = _stable_auth_module
        # None can't be encoded -> falls into the generic except -> False
        assert am.verify_password(None, "$2b$12$abc") is False

    def test_get_password_hash_rejects_over_72_bytes(self, _stable_auth_module):
        am = _stable_auth_module
        with pytest.raises(ValueError, match="72-byte"):
            am.get_password_hash("x" * 80)

    def test_get_password_hash_accepts_bytes_input(self, _stable_auth_module):
        am = _stable_auth_module
        h = am.get_password_hash(b"bytes-password")
        assert am.verify_password("bytes-password", h) is True

    def test_verify_password_non_bytes_hash_returns_false(self, _stable_auth_module):
        """A non-str/non-bytes hash (e.g. None or int) → False (no crash)."""
        am = _stable_auth_module
        assert am.verify_password("secret", None) is False
        assert am.verify_password("secret", 12345) is False

    def test_verify_password_generic_exception_returns_false(self, _stable_auth_module, monkeypatch):
        """A non-ValueError exception from bcrypt.checkpw (e.g. TypeError) is
        caught by the generic except → False."""
        am = _stable_auth_module
        h = am.get_password_hash("secret")
        with patch.object(am.bcrypt, "checkpw", side_effect=RuntimeError("boom")):
            assert am.verify_password("secret", h) is False


def test_production_requires_secret_key():
    """BUG coverage: in production with no SECRET_KEY, importing core.auth must
    raise ValueError (fail-closed) rather than silently generating a dev key.

    Run in a subprocess so the import-time check (which only fires on module
    load) executes against a clean environment without polluting this session's
    already-imported core.auth module.
    """
    import subprocess
    env = {
        **os.environ,
        "ENVIRONMENT": "production",
        "SECRET_KEY": "",
        "JWT_SECRET": "",
    }
    # PYTHONPATH must include backend/ so `import core.auth` resolves.
    env["PYTHONPATH"] = "/Users/rushiparikh/projects/atom/backend" + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-c", "import core.auth"],
        env=env, capture_output=True, text=True,
    )
    assert result.returncode != 0, (
        "core.auth must fail-closed in production with no SECRET_KEY"
    )
    assert "SECRET_KEY" in result.stderr


# ===========================================================================
# create_access_token / generate_satellite_key
# ===========================================================================


class TestCreateAccessToken:
    def test_includes_jti(self, _stable_auth_module):
        am = _stable_auth_module
        tok = am.create_access_token({"sub": "u1"})
        payload = jwt.decode(tok, am.SECRET_KEY, algorithms=[am.ALGORITHM])
        assert "jti" in payload
        assert payload["sub"] == "u1"

    def test_distinct_jti_per_call(self, _stable_auth_module):
        am = _stable_auth_module
        t1 = jwt.decode(am.create_access_token({"sub": "u1"}), am.SECRET_KEY, algorithms=[am.ALGORITHM])["jti"]
        t2 = jwt.decode(am.create_access_token({"sub": "u1"}), am.SECRET_KEY, algorithms=[am.ALGORITHM])["jti"]
        assert t1 != t2

    def test_custom_expires_delta(self, _stable_auth_module):
        am = _stable_auth_module
        tok = am.create_access_token({"sub": "u1"}, expires_delta=timedelta(hours=2))
        payload = jwt.decode(tok, am.SECRET_KEY, algorithms=[am.ALGORITHM])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert timedelta(hours=1, minutes=55) < (exp - datetime.now(timezone.utc)) < timedelta(hours=2, minutes=5)


class TestSatelliteKey:
    def test_format_and_uniqueness(self, _stable_auth_module):
        am = _stable_auth_module
        k1 = am.generate_satellite_key()
        k2 = am.generate_satellite_key()
        assert k1.startswith("sk-")
        assert k2.startswith("sk-")
        assert k1 != k2
        assert len(k1) == len("sk-") + 48  # 24 bytes hex


# ===========================================================================
# In-memory token revocation
# ===========================================================================


class TestRevocationList:
    def test_revoke_and_check(self, _stable_auth_module):
        am = _stable_auth_module
        am._revoked_tokens.clear()
        am._revoked_expiry.clear()
        exp = int(datetime.now(timezone.utc).timestamp()) + 1000
        am.revoke_token("jti-1", exp)
        assert am.is_token_revoked("jti-1") is True

    def test_non_revoked(self, _stable_auth_module):
        am = _stable_auth_module
        am._revoked_tokens.clear()
        am._revoked_expiry.clear()
        assert am.is_token_revoked("not-revoked") is False

    def test_none_jti_not_revoked(self, _stable_auth_module):
        am = _stable_auth_module
        assert am.is_token_revoked(None) is False

    def test_empty_jti_not_revoked(self, _stable_auth_module):
        am = _stable_auth_module
        assert am.is_token_revoked("") is False

    def test_expired_revocation_pruned(self, _stable_auth_module):
        am = _stable_auth_module
        am._revoked_tokens.clear()
        am._revoked_expiry.clear()
        # Add an already-expired revocation
        past_exp = int(datetime.now(timezone.utc).timestamp()) - 100
        am.revoke_token("expired-jti", past_exp)
        # Looking it up triggers pruning → returns False and removes it
        assert am.is_token_revoked("expired-jti") is False
        assert "expired-jti" not in am._revoked_tokens
        assert "expired-jti" not in am._revoked_expiry

    def test_pruning_keeps_active(self, _stable_auth_module):
        am = _stable_auth_module
        am._revoked_tokens.clear()
        am._revoked_expiry.clear()
        future_exp = int(datetime.now(timezone.utc).timestamp()) + 1000
        past_exp = int(datetime.now(timezone.utc).timestamp()) - 100
        am.revoke_token("active-jti", future_exp)
        am.revoke_token("expired-jti", past_exp)
        assert am.is_token_revoked("active-jti") is True
        assert "expired-jti" not in am._revoked_expiry


# ===========================================================================
# get_current_user — every branch
# ===========================================================================


class TestGetCurrentUser:
    def _run(self, am, **kw):
        return asyncio.run(am.get_current_user(**kw))

    def test_valid_token_header(self, _stable_auth_module):
        am = _stable_auth_module
        user = _make_user()
        tok = _make_token(am)
        req = MagicMock(); req.cookies = {}
        db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = user
        assert self._run(am, request=req, token=tok, db=db) is user

    def test_quoted_token_unwrapped(self, _stable_auth_module):
        am = _stable_auth_module
        user = _make_user()
        tok = '"' + _make_token(am) + '"'
        req = MagicMock(); req.cookies = {}
        db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = user
        assert self._run(am, request=req, token=tok, db=db) is user

    def test_cookie_fallback(self, _stable_auth_module):
        am = _stable_auth_module
        user = _make_user()
        tok = _make_token(am)
        req = MagicMock(); req.cookies = {"next-auth.session-token": tok}
        db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = user
        assert self._run(am, request=req, token=None, db=db) is user

    def test_secure_cookie_fallback(self, _stable_auth_module):
        am = _stable_auth_module
        user = _make_user()
        tok = _make_token(am)
        req = MagicMock(); req.cookies = {"__Secure-next-auth.session-token": tok}
        db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = user
        assert self._run(am, request=req, token=None, db=db) is user

    def test_no_token_raises_401(self, _stable_auth_module):
        am = _stable_auth_module
        req = MagicMock(); req.cookies = {}
        db = MagicMock()
        with pytest.raises(HTTPException) as exc:
            self._run(am, request=req, token=None, db=db)
        assert exc.value.status_code == 401

    def test_bad_format_token_raises_401(self, _stable_auth_module):
        am = _stable_auth_module
        req = MagicMock(); req.cookies = {}
        db = MagicMock()
        with pytest.raises(HTTPException) as exc:
            self._run(am, request=req, token="no-dots", db=db)
        assert exc.value.status_code == 401

    def test_invalid_signature_raises_401(self, _stable_auth_module):
        am = _stable_auth_module
        bad = jwt.encode({"sub": "u1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "WRONG", algorithm="HS256")
        req = MagicMock(); req.cookies = {}
        db = MagicMock()
        with pytest.raises(HTTPException) as exc:
            self._run(am, request=req, token=bad, db=db)
        assert exc.value.status_code == 401

    def test_missing_subject_claim_raises_401(self, _stable_auth_module):
        am = _stable_auth_module
        tok = jwt.encode({"exp": datetime.now(timezone.utc) + timedelta(hours=1)}, am.SECRET_KEY, algorithm=am.ALGORITHM)
        req = MagicMock(); req.cookies = {}
        db = MagicMock()
        with pytest.raises(HTTPException) as exc:
            self._run(am, request=req, token=tok, db=db)
        assert exc.value.status_code == 401

    def test_user_id_claim_fallback(self, _stable_auth_module):
        am = _stable_auth_module
        user = _make_user()
        tok = jwt.encode({"user_id": user.id, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, am.SECRET_KEY, algorithm=am.ALGORITHM)
        req = MagicMock(); req.cookies = {}
        db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = user
        assert self._run(am, request=req, token=tok, db=db) is user

    def test_id_claim_fallback(self, _stable_auth_module):
        am = _stable_auth_module
        user = _make_user()
        tok = jwt.encode({"id": user.id, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, am.SECRET_KEY, algorithm=am.ALGORITHM)
        req = MagicMock(); req.cookies = {}
        db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = user
        assert self._run(am, request=req, token=tok, db=db) is user

    def test_user_not_found_raises_401(self, _stable_auth_module):
        am = _stable_auth_module
        tok = _make_token(am)
        req = MagicMock(); req.cookies = {}
        db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc:
            self._run(am, request=req, token=tok, db=db)
        assert exc.value.status_code == 401

    def test_suspended_user_raises_401(self, _stable_auth_module):
        am = _stable_auth_module
        user = _make_user(status="suspended")
        tok = _make_token(am)
        req = MagicMock(); req.cookies = {}
        db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = user
        with pytest.raises(HTTPException) as exc:
            self._run(am, request=req, token=tok, db=db)
        assert exc.value.status_code == 401

    def test_revoked_token_raises_401(self, _stable_auth_module):
        am = _stable_auth_module
        user = _make_user()
        tok = _make_token(am, jti="rev-jti")
        am._revoked_tokens.clear(); am._revoked_expiry.clear()
        am.revoke_token("rev-jti", int(datetime.now(timezone.utc).timestamp()) + 1000)
        req = MagicMock(); req.cookies = {}
        db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = user
        with pytest.raises(HTTPException) as exc:
            self._run(am, request=req, token=tok, db=db)
        assert exc.value.status_code == 401


# ===========================================================================
# get_current_tenant
# ===========================================================================


class TestGetCurrentTenant:
    def _run(self, am, current_user, db):
        return asyncio.run(am.get_current_tenant(current_user=current_user, db=db))

    def test_resolves_tenant_by_id(self, _stable_auth_module):
        am = _stable_auth_module
        user = _make_user()
        tenant = MagicMock(id="t1")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = tenant
        with patch("core.personal_scope.resolve_tenant_id", return_value="t1"):
            result = self._run(am, user, db)
        assert result is tenant

    def test_falls_back_to_first_tenant(self, _stable_auth_module):
        am = _stable_auth_module
        user = _make_user()
        tenant = MagicMock(id="default")
        db = MagicMock()
        # First query (by id) returns None, second query (.first()) returns tenant
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.first.return_value = tenant
        with patch("core.personal_scope.resolve_tenant_id", return_value="missing"):
            result = self._run(am, user, db)
        assert result is tenant

    def test_no_tenant_raises_404(self, _stable_auth_module):
        am = _stable_auth_module
        user = _make_user()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.first.return_value = None
        with patch("core.personal_scope.resolve_tenant_id", return_value="missing"):
            with pytest.raises(HTTPException) as exc:
                self._run(am, user, db)
        assert exc.value.status_code == 404


# ===========================================================================
# get_current_user_ws
# ===========================================================================


class TestGetCurrentUserWs:
    def _run(self, am, token, db):
        return asyncio.run(am.get_current_user_ws(token, db))

    def test_valid(self, _stable_auth_module):
        am = _stable_auth_module
        user = _make_user()
        tok = _make_token(am)
        db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = user
        assert self._run(am, tok, db) is user

    def test_none_token(self, _stable_auth_module):
        am = _stable_auth_module
        db = MagicMock()
        assert self._run(am, None, db) is None

    def test_bad_format(self, _stable_auth_module):
        am = _stable_auth_module
        db = MagicMock()
        assert self._run(am, "no-dots", db) is None

    def test_invalid_signature(self, _stable_auth_module):
        am = _stable_auth_module
        bad = jwt.encode({"sub": "u1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "WRONG", algorithm="HS256")
        db = MagicMock()
        assert self._run(am, bad, db) is None

    def test_missing_subject(self, _stable_auth_module):
        am = _stable_auth_module
        tok = jwt.encode({"exp": datetime.now(timezone.utc) + timedelta(hours=1)}, am.SECRET_KEY, algorithm=am.ALGORITHM)
        db = MagicMock()
        assert self._run(am, tok, db) is None

    def test_suspended_user(self, _stable_auth_module):
        am = _stable_auth_module
        user = _make_user(status="suspended")
        tok = _make_token(am)
        db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = user
        assert self._run(am, tok, db) is None

    def test_user_not_found(self, _stable_auth_module):
        am = _stable_auth_module
        tok = _make_token(am)
        db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = None
        assert self._run(am, tok, db) is None

    def test_revoked_token(self, _stable_auth_module):
        am = _stable_auth_module
        user = _make_user()
        tok = _make_token(am, jti="ws-rev")
        am._revoked_tokens.clear(); am._revoked_expiry.clear()
        am.revoke_token("ws-rev", int(datetime.now(timezone.utc).timestamp()) + 1000)
        db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = user
        assert self._run(am, tok, db) is None


# ===========================================================================
# decode_token
# ===========================================================================


class TestDecodeToken:
    def test_valid(self, _stable_auth_module):
        am = _stable_auth_module
        tok = _make_token(am)
        assert am.decode_token(tok)["sub"] == "u-1"

    def test_none(self, _stable_auth_module):
        am = _stable_auth_module
        assert am.decode_token(None) is None

    def test_empty(self, _stable_auth_module):
        am = _stable_auth_module
        assert am.decode_token("") is None

    def test_bad_format(self, _stable_auth_module):
        am = _stable_auth_module
        assert am.decode_token("no-dots") is None

    def test_wrong_signature(self, _stable_auth_module):
        am = _stable_auth_module
        bad = jwt.encode({"sub": "u1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "WRONG", algorithm="HS256")
        assert am.decode_token(bad) is None

    def test_revoked(self, _stable_auth_module):
        am = _stable_auth_module
        tok = _make_token(am, jti="dec-rev")
        am._revoked_tokens.clear(); am._revoked_expiry.clear()
        am.revoke_token("dec-rev", int(datetime.now(timezone.utc).timestamp()) + 1000)
        assert am.decode_token(tok) is None

    def test_expired(self, _stable_auth_module):
        am = _stable_auth_module
        tok = jwt.encode({"sub": "u1", "exp": datetime.now(timezone.utc) - timedelta(hours=1)}, am.SECRET_KEY, algorithm=am.ALGORITHM)
        assert am.decode_token(tok) is None

    def test_unexpected_exception_returns_none(self, _stable_auth_module, monkeypatch):
        """A non-JWTError exception is caught by the generic except → None."""
        am = _stable_auth_module
        tok = _make_token(am)

        def boom(*a, **k):
            raise RuntimeError("unexpected")

        monkeypatch.setattr(am.jwt, "decode", boom)
        assert am.decode_token(tok) is None


# ===========================================================================
# verify_mobile_token + bug-hunt (status check missing)
# ===========================================================================


def _mobile_token(am, sub="u-1"):
    return jwt.encode({"sub": sub, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, am.SECRET_KEY, algorithm=am.ALGORITHM)


class TestVerifyMobileToken:
    def test_active_user(self, _stable_auth_module):
        am = _stable_auth_module
        user = _make_user(status="active")
        db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = user
        assert am.verify_mobile_token(_mobile_token(am), db) is user

    def test_missing_sub(self, _stable_auth_module):
        am = _stable_auth_module
        tok = jwt.encode({"exp": datetime.now(timezone.utc) + timedelta(hours=1)}, am.SECRET_KEY, algorithm=am.ALGORITHM)
        db = MagicMock()
        assert am.verify_mobile_token(tok, db) is None

    def test_invalid_token(self, _stable_auth_module):
        am = _stable_auth_module
        db = MagicMock()
        assert am.verify_mobile_token("bad.token.here", db) is None

    def test_jwt_error_returns_none(self, _stable_auth_module):
        am = _stable_auth_module
        bad = jwt.encode({"sub": "u1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "WRONG", algorithm="HS256")
        db = MagicMock()
        assert am.verify_mobile_token(bad, db) is None

    def test_suspended_user_rejected(self, _stable_auth_module):
        """BUG: verify_mobile_token returned a SUSPENDED user as valid. It must
        reject non-ACTIVE users, mirroring get_current_user / get_current_user_ws
        / authenticate_mobile_user — otherwise a suspended user's existing 24h
        mobile JWT keeps authenticating them."""
        am = _stable_auth_module
        user = _make_user(status="suspended")
        db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = user
        assert am.verify_mobile_token(_mobile_token(am), db) is None, (
            "Suspended user was accepted by verify_mobile_token — status check missing."
        )

    def test_deleted_user_rejected(self, _stable_auth_module):
        """BUG: same gap — a DELETED user must not authenticate via mobile token."""
        am = _stable_auth_module
        user = _make_user(status="deleted")
        db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = user
        assert am.verify_mobile_token(_mobile_token(am), db) is None


# ===========================================================================
# get_mobile_device
# ===========================================================================


class TestGetMobileDevice:
    def test_active_device(self, _stable_auth_module):
        am = _stable_auth_module
        dev = MagicMock(status="active")
        db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = dev
        assert am.get_mobile_device("d1", "u1", db) is dev

    def test_inactive_device_returns_none(self, _stable_auth_module):
        am = _stable_auth_module
        dev = MagicMock(status="revoked")
        db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = dev
        assert am.get_mobile_device("d1", "u1", db) is None

    def test_no_device(self, _stable_auth_module):
        am = _stable_auth_module
        db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = None
        assert am.get_mobile_device("d1", "u1", db) is None


# ===========================================================================
# create_mobile_token
# ===========================================================================


class TestCreateMobileToken:
    def test_default_expiries(self, _stable_auth_module):
        am = _stable_auth_module
        user = _make_user()
        tokens = am.create_mobile_token(user, "dev-1")
        assert tokens["token_type"] == "bearer"
        access = jwt.decode(tokens["access_token"], am.SECRET_KEY, algorithms=[am.ALGORITHM])
        refresh = jwt.decode(tokens["refresh_token"], am.SECRET_KEY, algorithms=[am.ALGORITHM])
        assert access["sub"] == str(user.id)
        assert access["device_id"] == "dev-1"
        assert access["platform"] == "mobile"
        assert refresh["type"] == "refresh"
        assert refresh["device_id"] == "dev-1"
        assert refresh["exp"] > access["exp"]  # refresh outlives access

    def test_custom_expiry(self, _stable_auth_module):
        am = _stable_auth_module
        user = _make_user()
        tokens = am.create_mobile_token(user, "dev-2", expires_delta=timedelta(hours=1))
        access = jwt.decode(tokens["access_token"], am.SECRET_KEY, algorithms=[am.ALGORITHM])
        exp = datetime.fromtimestamp(access["exp"], tz=timezone.utc)
        assert timedelta(minutes=55) < (exp - datetime.now(timezone.utc)) < timedelta(hours=1, minutes=5)


# ===========================================================================
# authenticate_mobile_user
# ===========================================================================


class TestAuthenticateMobileUser:
    def _run(self, am, **kw):
        return asyncio.run(am.authenticate_mobile_user(**kw))

    def test_success_new_device(self, _stable_auth_module):
        am = _stable_auth_module
        user = _make_user()
        user.hashed_password = am.get_password_hash("ValidPass123!")
        db = MagicMock()
        # First query (User by email) returns user; second query (MobileDevice
        # by device_token) returns None → new device is created.
        user_query = MagicMock(); user_query.filter.return_value.first.return_value = user
        dev_query = MagicMock(); dev_query.filter.return_value.first.return_value = None
        db.query.side_effect = [user_query, dev_query]
        result = self._run(am, email="u@x", password="ValidPass123!", device_token="dt1", platform="ios", db=db)
        assert result is not None
        assert result["user"]["id"] == str(user.id)
        assert "access_token" in result
        db.add.assert_called()  # new device added

    def test_unknown_user(self, _stable_auth_module):
        am = _stable_auth_module
        db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = None
        result = self._run(am, email="no@x", password="p", device_token="dt", platform="ios", db=db)
        assert result is None

    def test_suspended_user(self, _stable_auth_module):
        am = _stable_auth_module
        user = _make_user(status="suspended")
        db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = user
        result = self._run(am, email="u@x", password="p", device_token="dt", platform="ios", db=db)
        assert result is None

    def test_wrong_password(self, _stable_auth_module):
        am = _stable_auth_module
        user = _make_user()
        user.hashed_password = am.get_password_hash("CorrectPass123!")
        db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = user
        result = self._run(am, email="u@x", password="WrongPass123!", device_token="dt", platform="ios", db=db)
        assert result is None

    def test_existing_device_updated(self, _stable_auth_module):
        am = _stable_auth_module
        user = _make_user()
        user.hashed_password = am.get_password_hash("ValidPass123!")
        existing_dev = MagicMock(id="dev-exist", status="inactive", platform="android")
        # First query (User) returns user; second query (MobileDevice) returns existing_dev
        db = MagicMock()
        user_query = MagicMock(); user_query.filter.return_value.first.return_value = user
        dev_query = MagicMock(); dev_query.filter.return_value.first.return_value = existing_dev
        db.query.side_effect = [user_query, dev_query]
        result = self._run(am, email="u@x", password="ValidPass123!", device_token="dt", platform="ios", db=db)
        assert result is not None
        assert existing_dev.status == "active"
        assert existing_dev.platform == "ios"


# ===========================================================================
# verify_biometric_signature
# ===========================================================================


class TestVerifyBiometricSignature:
    @pytest.fixture(scope="class")
    def ec_keypair(self):
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

        key = ec.generate_private_key(ec.SECP256R1())
        pub_pem = key.public_key().public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        ).decode()

        def sign(challenge: str) -> str:
            sig = key.sign(challenge.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
            return base64.b64encode(sig).decode()

        return pub_pem, sign

    def test_valid_ec_signature(self, _stable_auth_module, ec_keypair):
        am = _stable_auth_module
        pub, sign = ec_keypair
        assert am.verify_biometric_signature(sign("challenge"), pub, "challenge") is True

    def test_wrong_challenge(self, _stable_auth_module, ec_keypair):
        am = _stable_auth_module
        pub, sign = ec_keypair
        assert am.verify_biometric_signature(sign("real"), pub, "forged") is False

    def test_invalid_signature(self, _stable_auth_module, ec_keypair):
        am = _stable_auth_module
        pub, _ = ec_keypair
        assert am.verify_biometric_signature("not-base64-signature", pub, "challenge") is False

    def test_invalid_public_key(self, _stable_auth_module):
        am = _stable_auth_module
        assert am.verify_biometric_signature("sig", "not-a-key", "challenge") is False

    def test_empty_inputs(self, _stable_auth_module):
        am = _stable_auth_module
        assert am.verify_biometric_signature("", "pub", "challenge") is False
        assert am.verify_biometric_signature(None, "pub", "challenge") is False

    def test_rsa_key_accepted(self, _stable_auth_module):
        """An RSA keypair with PSS padding should also verify (the fallback)."""
        from cryptography.hazmat.primitives.asymmetric import rsa, padding
        from cryptography.hazmat.primitives import hashes, serialization

        am = _stable_auth_module
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub_pem = key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        sig = key.sign(
            b"challenge",
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        sig_b64 = base64.b64encode(sig).decode()
        assert am.verify_biometric_signature(sig_b64, pub_pem, "challenge") is True


# ===========================================================================
# core/auth_helpers.py — error / bypass branches
# ===========================================================================


class TestAuthHelpersVerifyJwt:
    def test_valid_token(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET", "helpers-secret")
        from core.auth_helpers import verify_jwt_token
        tok = jwt.encode({"sub": "u1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "helpers-secret", algorithm="HS256")
        assert verify_jwt_token(tok)["sub"] == "u1"

    def test_missing_sub_claim(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET", "helpers-secret")
        from core.auth_helpers import verify_jwt_token
        tok = jwt.encode({"exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "helpers-secret", algorithm="HS256")
        with pytest.raises(HTTPException) as exc:
            verify_jwt_token(tok)
        assert exc.value.status_code == 401
        assert "subject" in exc.value.detail.lower()

    def test_expired(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET", "helpers-secret")
        from core.auth_helpers import verify_jwt_token
        tok = jwt.encode({"sub": "u1", "exp": datetime.now(timezone.utc) - timedelta(hours=1)}, "helpers-secret", algorithm="HS256")
        with pytest.raises(HTTPException) as exc:
            verify_jwt_token(tok)
        assert exc.value.detail == "Token expired"

    def test_invalid_token(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET", "helpers-secret")
        from core.auth_helpers import verify_jwt_token
        with pytest.raises(HTTPException) as exc:
            verify_jwt_token("not.a.jwt")
        assert exc.value.status_code == 401
        assert exc.value.detail == "Invalid token"

    def test_no_secret_no_bypass_500(self, monkeypatch):
        for k in ("JWT_SECRET", "SECRET_KEY", "EMERGENCY_GOVERNANCE_BYPASS"):
            monkeypatch.delenv(k, raising=False)
        from core.auth_helpers import verify_jwt_token
        with pytest.raises(HTTPException) as exc:
            verify_jwt_token("any")
        assert exc.value.status_code == 500
        assert "not configured" in exc.value.detail.lower()

    def test_emergency_bypass_allows_bad_token(self, monkeypatch):
        """EMERGENCY_GOVERNANCE_BYPASS=true returns an emergency_user payload
        for an otherwise-invalid token (intentional emergency feature)."""
        monkeypatch.setenv("JWT_SECRET", "helpers-secret")
        monkeypatch.setenv("EMERGENCY_GOVERNANCE_BYPASS", "true")
        from core.auth_helpers import verify_jwt_token
        bad = jwt.encode({"sub": "x", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "WRONG", algorithm="HS256")
        result = verify_jwt_token(bad)
        assert result["user_id"] == "emergency_user"
        assert result["bypass"] is True

    def test_emergency_bypass_no_secret(self, monkeypatch):
        for k in ("JWT_SECRET", "SECRET_KEY"):
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setenv("EMERGENCY_GOVERNANCE_BYPASS", "true")
        from core.auth_helpers import verify_jwt_token
        result = verify_jwt_token("any-token")
        assert result["user_id"] == "emergency_user"

    def test_generic_exception_bypass(self, monkeypatch):
        """A non-JWTError, non-HTTPException exception still triggers bypass
        when enabled (the second bypass branch)."""
        monkeypatch.setenv("JWT_SECRET", "helpers-secret")
        monkeypatch.setenv("EMERGENCY_GOVERNANCE_BYPASS", "true")
        from core.auth_helpers import verify_jwt_token
        with patch("core.auth_helpers.jwt.decode", side_effect=RuntimeError("boom")):
            result = verify_jwt_token("any-token")
        assert result["user_id"] == "emergency_user"

    def test_generic_exception_no_bypass_401(self, monkeypatch):
        """Without bypass, a generic exception becomes a 401."""
        monkeypatch.setenv("JWT_SECRET", "helpers-secret")
        monkeypatch.delenv("EMERGENCY_GOVERNANCE_BYPASS", raising=False)
        from core.auth_helpers import verify_jwt_token
        with patch("core.auth_helpers.jwt.decode", side_effect=RuntimeError("boom")):
            with pytest.raises(HTTPException) as exc:
                verify_jwt_token("any-token")
        assert exc.value.status_code == 401
        assert exc.value.detail == "Authentication failed"


class TestAuthHelpersUserResolution:
    def test_require_user_no_db_returns_minimal(self, monkeypatch):
        from core.auth_helpers import require_authenticated_user
        # No db session → returns a minimal User (less secure path)
        result = asyncio.run(require_authenticated_user("some-id", None, allow_default=False))
        assert result.id == "some-id"

    def test_require_user_default_no_db_raises(self, monkeypatch):
        from core.auth_helpers import require_authenticated_user
        with pytest.raises(HTTPException) as exc:
            asyncio.run(require_authenticated_user("default_user", None, allow_default=True))
        assert exc.value.status_code == 401

    def test_require_user_default_db_no_admin_raises(self, monkeypatch):
        from core.auth_helpers import require_authenticated_user
        db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc:
            asyncio.run(require_authenticated_user("default_user", db, allow_default=True))
        assert exc.value.status_code == 401

    def test_get_optional_user_no_db(self, monkeypatch):
        from core.auth_helpers import get_optional_user
        result = asyncio.run(get_optional_user("some-id", None))
        assert result.id == "some-id"

    def test_get_optional_user_default(self, monkeypatch):
        from core.auth_helpers import get_optional_user
        assert asyncio.run(get_optional_user("default_user", None)) is None

    def test_validate_user_context_passes(self):
        from core.auth_helpers import validate_user_context
        validate_user_context("u1", "op")  # no raise

    def test_validate_user_context_none(self):
        from core.auth_helpers import validate_user_context
        with pytest.raises(HTTPException) as exc:
            validate_user_context(None, "op")
        assert exc.value.status_code == 401

    def test_validate_user_context_default(self):
        from core.auth_helpers import validate_user_context
        with pytest.raises(HTTPException) as exc:
            validate_user_context("default_user", "op")
        assert exc.value.status_code == 401
        assert "op" in exc.value.detail


class TestAuthHelpersCleanup:
    def test_cleanup_revoked_exception_returns_zero(self, monkeypatch):
        from core.auth_helpers import cleanup_expired_revoked_tokens
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        assert cleanup_expired_revoked_tokens(db) == 0
        db.rollback.assert_called()

    def test_cleanup_active_exception_returns_zero(self, monkeypatch):
        from core.auth_helpers import cleanup_expired_active_tokens
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        assert cleanup_expired_active_tokens(db) == 0
        db.rollback.assert_called()


class TestAuthHelpersRevocationErrors:
    def test_revoke_token_db_error_raises_500(self, monkeypatch):
        from core.auth_helpers import revoke_token
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        with pytest.raises(HTTPException) as exc:
            revoke_token("jti", datetime.now(timezone.utc), db, "u1")
        assert exc.value.status_code == 500
        db.rollback.assert_called()

    def test_revoke_all_tokens_db_error_raises_500(self, monkeypatch):
        from core.auth_helpers import revoke_all_user_tokens
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        with pytest.raises(HTTPException) as exc:
            revoke_all_user_tokens("u1", db)
        assert exc.value.status_code == 500

    def test_track_active_token_db_error_raises_500(self, monkeypatch):
        from core.auth_helpers import track_active_token
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        with pytest.raises(HTTPException) as exc:
            track_active_token("jti", "u1", datetime.now(timezone.utc), db)
        assert exc.value.status_code == 500


# ===========================================================================
# auth_helpers DB-backed happy paths (self-contained in-memory SQLite session)
# ===========================================================================


@pytest.fixture(scope="module")
def helpers_db():
    """In-memory SQLite session for auth_helpers DB-backed functions, so this
    file is self-sufficient (doesn't depend on tests/unit/security/test_auth_helpers.py)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from core.database import Base as _Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _Base.metadata.create_all(bind=engine, checkfirst=True)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


class TestAuthHelpersDbHappyPaths:
    def test_revoke_token_success(self, helpers_db):
        from core.auth_helpers import revoke_token
        from core.models import RevokedToken
        jti = "happy-jti-1"
        result = revoke_token(jti, datetime.now(timezone.utc) + timedelta(hours=1), helpers_db, user_id="u1", revocation_reason="logout")
        assert result is True
        rt = helpers_db.query(RevokedToken).filter_by(jti=jti).first()
        assert rt is not None
        assert rt.reason == "logout"

    def test_revoke_token_already_revoked_returns_false(self, helpers_db):
        from core.auth_helpers import revoke_token
        jti = "happy-jti-2"
        revoke_token(jti, datetime.now(timezone.utc) + timedelta(hours=1), helpers_db, user_id="u1")
        result = revoke_token(jti, datetime.now(timezone.utc) + timedelta(hours=1), helpers_db, user_id="u1")
        assert result is False

    def test_track_active_token_success(self, helpers_db):
        from core.auth_helpers import track_active_token
        from core.models import ActiveToken
        jti = "track-jti-1"
        result = track_active_token(jti, "u1", datetime.now(timezone.utc) + timedelta(hours=1), helpers_db, issued_ip="1.2.3.4", issued_user_agent="ua")
        assert result is True
        at = helpers_db.query(ActiveToken).filter_by(jti=jti).first()
        assert at is not None
        assert at.issued_ip == "1.2.3.4"
        assert at.issued_user_agent == "ua"

    def test_track_active_token_duplicate_returns_false(self, helpers_db):
        from core.auth_helpers import track_active_token
        jti = "track-jti-2"
        track_active_token(jti, "u1", datetime.now(timezone.utc) + timedelta(hours=1), helpers_db)
        result = track_active_token(jti, "u1", datetime.now(timezone.utc) + timedelta(hours=1), helpers_db)
        assert result is False

    def test_revoke_all_user_tokens_success(self, helpers_db):
        from core.auth_helpers import revoke_all_user_tokens
        from core.models import ActiveToken
        uid = "revoke-all-u1"
        for i in range(3):
            helpers_db.add(ActiveToken(jti=f"all-{i}", user_id=uid, expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        helpers_db.commit()
        count = revoke_all_user_tokens(uid, helpers_db, revocation_reason="password_change")
        assert count == 3
        # All moved out of active
        remaining = helpers_db.query(ActiveToken).filter(ActiveToken.user_id == uid).all()
        assert remaining == []

    def test_revoke_all_user_tokens_with_except(self, helpers_db):
        from core.auth_helpers import revoke_all_user_tokens
        from core.models import ActiveToken
        uid = "revoke-all-u2"
        helpers_db.add(ActiveToken(jti="keep", user_id=uid, expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        helpers_db.add(ActiveToken(jti="drop", user_id=uid, expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        helpers_db.commit()
        count = revoke_all_user_tokens(uid, helpers_db, except_jti="keep")
        assert count == 1

    def test_revoke_all_user_tokens_no_tokens(self, helpers_db):
        from core.auth_helpers import revoke_all_user_tokens
        assert revoke_all_user_tokens("nonexistent-user", helpers_db) == 0

    def test_cleanup_expired_revoked_success(self, helpers_db):
        from core.auth_helpers import cleanup_expired_revoked_tokens
        from core.models import RevokedToken
        helpers_db.add(RevokedToken(jti="old-rev", expires_at=datetime.now(timezone.utc) - timedelta(hours=2), user_id="u1", reason="logout"))
        helpers_db.add(RevokedToken(jti="new-rev", expires_at=datetime.now(timezone.utc) + timedelta(hours=1), user_id="u1", reason="logout"))
        helpers_db.commit()
        deleted = cleanup_expired_revoked_tokens(helpers_db, older_than_hours=1)
        assert deleted == 1

    def test_cleanup_expired_active_success(self, helpers_db):
        from core.auth_helpers import cleanup_expired_active_tokens
        from core.models import ActiveToken
        helpers_db.add(ActiveToken(jti="old-act", user_id="u1", expires_at=datetime.now(timezone.utc) - timedelta(hours=2)))
        helpers_db.add(ActiveToken(jti="new-act", user_id="u1", expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        helpers_db.commit()
        deleted = cleanup_expired_active_tokens(helpers_db, older_than_hours=1)
        assert deleted == 1

    def test_require_user_db_lookup_success(self, helpers_db):
        from core.auth_helpers import require_authenticated_user
        from core.models import User
        u = User(id="req-u1", email="req@x", hashed_password="h", first_name="A", last_name="B", role="member", status="active")
        helpers_db.add(u); helpers_db.commit()
        result = asyncio.run(require_authenticated_user("req-u1", helpers_db, allow_default=False))
        assert result.id == "req-u1"

    def test_require_user_default_disallowed_no_db_raises(self, helpers_db):
        """default_user with allow_default=False → 401 (the else branch)."""
        from core.auth_helpers import require_authenticated_user
        with pytest.raises(HTTPException) as exc:
            asyncio.run(require_authenticated_user("default_user", helpers_db, allow_default=False))
        assert exc.value.status_code == 401

    def test_require_user_db_lookup_not_found_404(self, helpers_db):
        """A user_id not in the DB → 404."""
        from core.auth_helpers import require_authenticated_user
        with pytest.raises(HTTPException) as exc:
            asyncio.run(require_authenticated_user("definitely-missing-id", helpers_db, allow_default=False))
        assert exc.value.status_code == 404

    def test_require_user_db_default_admin_fallback(self, helpers_db):
        from core.auth_helpers import require_authenticated_user
        from core.models import User
        u = User(id="admin-def", email="admin@atom.ai", hashed_password="h", first_name="A", last_name="B", role="member", status="active")
        helpers_db.add(u); helpers_db.commit()
        result = asyncio.run(require_authenticated_user("default_user", helpers_db, allow_default=True))
        assert result.email == "admin@atom.ai"

    def test_get_optional_user_db_lookup(self, helpers_db):
        from core.auth_helpers import get_optional_user
        from core.models import User
        u = User(id="opt-u1", email="opt@x", hashed_password="h", first_name="A", last_name="B", role="member", status="active")
        helpers_db.add(u); helpers_db.commit()
        result = asyncio.run(get_optional_user("opt-u1", helpers_db))
        assert result.id == "opt-u1"
        assert asyncio.run(get_optional_user("missing-id", helpers_db)) is None

    def test_revoke_all_skips_already_revoked(self, monkeypatch):
        """revoke_all_user_tokens skips tokens already in the revoked list."""
        from core.auth_helpers import revoke_all_user_tokens, RevokedToken, ActiveToken
        # Two active tokens; "j1" is already in the revoked set.
        t1 = ActiveToken(jti="j1", user_id="u1", expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        t2 = ActiveToken(jti="j2", user_id="u1", expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        already_revoked_jtis = {"j1"}
        added = []
        deleted = []

        class ActiveQ:
            def __init__(self, items): self._items = items
            def filter(self, *a, **k): return self  # user_id filter
            def all(self): return list(self._items)

        class RevokedQ:
            def __init__(self, jti): self._jti = jti
            def filter_by(self, **k): return self  # jti filter
            def first(self):
                return object() if self._jti in already_revoked_jtis else None

        class DB:
            def __init__(self): self._active_items = [t1, t2]
            def query(self, model):
                if model is ActiveToken:
                    return ActiveQ(self._active_items)
                # RevokedToken — needs per-jti lookup, so capture the jti
                return _RevokedTokenQuery(already_revoked_jtis)
            def add(self, obj): added.append(obj)
            def delete(self, obj): deleted.append(obj)
            def commit(self): pass
            def rollback(self): pass

        class _RevokedTokenQuery:
            def __init__(self, revoked_set): self._revoked = revoked_set
            def filter_by(self, **k):
                jti = k.get("jti")
                return _RevokedFirst(jti in self._revoked)
        class _RevokedFirst:
            def __init__(self, found): self._found = found
            def first(self):
                if self._found:
                    m = MagicMock()
                    m.revoked_at = "2026-01-01"
                    return m
                return None

        db = DB()
        count = revoke_all_user_tokens("u1", db)
        # j1 already revoked → skipped; j2 revoked → count 1
        assert count == 1
        # Exactly one new RevokedToken added, one ActiveToken deleted
        assert len(added) == 1
        assert added[0].jti == "j2"
        assert len(deleted) == 1
        assert deleted[0].jti == "j2"
