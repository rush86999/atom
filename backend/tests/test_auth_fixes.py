"""
TDD regression tests for auth fixes (June 2026).

Two critical bugs were fixed:
1. JWT claim name mismatch — get_current_user only checked "sub"/"id" but
   EnterpriseAuthService issues tokens with "user_id" claim. Every authenticated
   endpoint rejected valid tokens.
2. SECRET_KEY mismatch — EnterpriseAuthService resolved its signing key from
   ENTERPRISE_JWT_SECRET (or a hardcoded default), while core/auth.py verified
   with SECRET_KEY. In dev (no env vars), keys diverged → all tokens invalid.

These tests guard against regression of both bugs.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_user():
    """A MagicMock standing in for a User ORM record."""
    u = MagicMock()
    u.id = "00000000-0000-0000-0000-000000000000"
    u.email = "admin@example.com"
    u.first_name = "Admin"
    u.last_name = "User"
    u.role = "workspace_admin"
    u.status = "active"
    return u


@pytest.fixture
def fake_request():
    """A MagicMock Request with no cookies."""
    req = MagicMock()
    req.cookies = {}
    req.headers = {}
    return req


@pytest.fixture
def clean_auth_env(monkeypatch):
    """Ensure core.auth picks up a known SECRET_KEY, not a random one."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-auth-fix-tests")
    # Force reimport of the module-level SECRET_KEY
    import importlib
    import core.auth as auth_mod

    importlib.reload(auth_mod)
    yield auth_mod
    # Restore original module
    importlib.reload(auth_mod)


# ---------------------------------------------------------------------------
# Bug 1: JWT claim name fallback (sub → id → user_id)
# ---------------------------------------------------------------------------


class TestJwtClaimNameFallback:
    """get_current_user must accept tokens with 'user_id' claim, not just 'sub'/'id'.

    Regression guard for commit 7b05fabc3 which added payload.get("user_id")
    to the fallback chain.
    """

    def _make_token(self, claim_name: str, user_id: str, secret: str) -> str:
        """Build a minimal JWT with the given claim name."""
        import jwt as pyjwt

        payload = {
            claim_name: user_id,
            "exp": 9999999999,
            "iat": 1,
            "type": "access",
        }
        return pyjwt.encode(payload, secret, algorithm="HS256")

    def test_accepts_user_id_claim(self, clean_auth_env, fake_user, fake_request):
        """Tokens with 'user_id' claim (EnterpriseAuthService format) must validate."""
        secret = clean_auth_env.SECRET_KEY
        token = self._make_token("user_id", fake_user.id, secret)

        # Patch the DB query to return our fake user
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = fake_user

        user = clean_auth_env.__dict__.get("get_current_user")
        # Call the async function
        import asyncio

        result = asyncio.run(
            clean_auth_env.get_current_user(
                request=fake_request, token=token, db=mock_db
            )
        )
        assert result is fake_user

    def test_accepts_sub_claim(self, clean_auth_env, fake_user, fake_request):
        """Standard JWT 'sub' claim still works."""
        secret = clean_auth_env.SECRET_KEY
        token = self._make_token("sub", fake_user.id, secret)

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = fake_user

        import asyncio

        result = asyncio.run(
            clean_auth_env.get_current_user(
                request=fake_request, token=token, db=mock_db
            )
        )
        assert result is fake_user

    def test_accepts_id_claim(self, clean_auth_env, fake_user, fake_request):
        """NextAuth 'id' claim still works."""
        secret = clean_auth_env.SECRET_KEY
        token = self._make_token("id", fake_user.id, secret)

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = fake_user

        import asyncio

        result = asyncio.run(
            clean_auth_env.get_current_user(
                request=fake_request, token=token, db=mock_db
            )
        )
        assert result is fake_user

    def test_rejects_token_with_no_known_claim(self, clean_auth_env, fake_request):
        """Token with only an unknown claim (e.g. 'foo') must 401."""
        secret = clean_auth_env.SECRET_KEY
        token = self._make_token("foo", "some-id", secret)

        mock_db = MagicMock()

        import asyncio

        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                clean_auth_env.get_current_user(
                    request=fake_request, token=token, db=mock_db
                )
            )
        assert exc.value.status_code == 401

    def test_rejects_token_with_missing_user(self, clean_auth_env, fake_request):
        """Token decodes but user_id doesn't match any DB record → 401."""
        secret = clean_auth_env.SECRET_KEY
        token = self._make_token("user_id", "nonexistent-uuid", secret)

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        import asyncio

        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                clean_auth_env.get_current_user(
                    request=fake_request, token=token, db=mock_db
                )
            )
        assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# Bug 2: SECRET_KEY unification in EnterpriseAuthService
# ---------------------------------------------------------------------------


class TestEnterpriseAuthSecretKeyUnification:
    """EnterpriseAuthService must fall back to SECRET_KEY/JWT_SECRET so its
    tokens validate against core/auth.py's verification key.

    Regression guard for commit 7b05fabc3.
    """

    def test_uses_enterprise_jwt_secret_when_set(self, monkeypatch):
        """Explicit ENTERPRISE_JWT_SECRET takes priority (backward compat)."""
        monkeypatch.setenv("ENTERPRISE_JWT_SECRET", "enterprise-specific-key")
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("JWT_SECRET", raising=False)

        from core.enterprise_auth_service import EnterpriseAuthService

        svc = EnterpriseAuthService()
        assert svc.secret_key == "enterprise-specific-key"

    def test_falls_back_to_secret_key(self, monkeypatch):
        """When ENTERPRISE_JWT_SECRET is unset, SECRET_KEY must be used.

        This is the fix — previously fell through to the hardcoded default,
        causing sign/verify key mismatch.
        """
        monkeypatch.delenv("ENTERPRISE_JWT_SECRET", raising=False)
        monkeypatch.setenv("SECRET_KEY", "unified-secret-from-dotenv")
        monkeypatch.delenv("JWT_SECRET", raising=False)

        from core.enterprise_auth_service import EnterpriseAuthService

        svc = EnterpriseAuthService()
        assert svc.secret_key == "unified-secret-from-dotenv"

    def test_falls_back_to_jwt_secret(self, monkeypatch):
        """When both ENTERPRISE_JWT_SECRET and SECRET_KEY are unset,
        JWT_SECRET is the next fallback."""
        monkeypatch.delenv("ENTERPRISE_JWT_SECRET", raising=False)
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.setenv("JWT_SECRET", "jwt-secret-alias")

        from core.enterprise_auth_service import EnterpriseAuthService

        svc = EnterpriseAuthService()
        assert svc.secret_key == "jwt-secret-alias"

    def test_explicit_argument_overrides_env(self, monkeypatch):
        """Explicit secret_key argument wins over all env vars."""
        monkeypatch.setenv("ENTERPRISE_JWT_SECRET", "from-env")
        monkeypatch.setenv("SECRET_KEY", "from-env-too")

        from core.enterprise_auth_service import EnterpriseAuthService

        svc = EnterpriseAuthService(secret_key="explicit-arg")
        assert svc.secret_key == "explicit-arg"

    def test_hardcoded_fallback_only_when_nothing_set(self, monkeypatch):
        """The hardcoded default is the last resort (dev convenience)."""
        monkeypatch.delenv("ENTERPRISE_JWT_SECRET", raising=False)
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("JWT_SECRET", raising=False)

        from core.enterprise_auth_service import EnterpriseAuthService

        svc = EnterpriseAuthService()
        assert svc.secret_key == "default-secret-key-change-in-production"


# ---------------------------------------------------------------------------
# Integration: sign + verify roundtrip (both paths use the same key)
# ---------------------------------------------------------------------------


class TestAuthRoundtripIntegration:
    """End-to-end: token issued by EnterpriseAuthService verifies in core.auth.

    This is the integration test that would have caught the original bug:
    sign with EnterpriseAuthService, verify with get_current_user.
    """

    def test_enterprise_token_validates_in_core_auth(
        self, clean_auth_env, fake_user, fake_request, monkeypatch
    ):
        """Token from EnterpriseAuthService.create_access_token must be
        accepted by core.auth.get_current_user."""
        # Ensure both sides read the same SECRET_KEY
        monkeypatch.setenv("SECRET_KEY", "integration-test-secret")
        import importlib

        import core.auth as auth_mod
        import core.enterprise_auth_service as eas_mod

        importlib.reload(auth_mod)
        importlib.reload(eas_mod)

        # Issue token via enterprise auth service
        svc = eas_mod.EnterpriseAuthService()
        token = svc.create_access_token(fake_user.id)

        # Verify via core.auth.get_current_user
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = fake_user

        import asyncio

        result = asyncio.run(
            auth_mod.get_current_user(
                request=fake_request, token=token, db=mock_db
            )
        )
        assert result is fake_user, (
            "Token issued by EnterpriseAuthService was rejected by "
            "core.auth.get_current_user — sign/verify key mismatch"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
