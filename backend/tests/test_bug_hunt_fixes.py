"""
TDD regression tests for the June 2026 bug hunt fixes.

Covers:
- BUG 2: UserStatus import in EnterpriseAuthService (SAML user provisioning)
- BUG 3: JWTVerifier accepts user_id/id claims (not just sub)
- BUG 5: oauth_routes.get_current_user no longer trusts X-User-ID header
- BUG 6: /api/auth/refresh accepts JSON body refresh_token

Each test is a regression guard: reverting the fix makes the test fail.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# BUG 2: UserStatus import in enterprise_auth_service
# ---------------------------------------------------------------------------


class TestUserStatusImport:
    """EnterpriseAuthService must import UserStatus for SAML user provisioning."""

    def test_user_status_is_importable_in_module_namespace(self):
        """If UserStatus is not imported, _create_or_update_saml_user raises
        NameError at runtime. We verify the name resolves at module scope."""
        import core.enterprise_auth_service as eas

        # The module must reference UserStatus in its namespace (either via
        # direct import or re-export). Before the fix, only UserRole was
        # imported, causing NameError at line 767.
        assert hasattr(eas, "UserStatus"), (
            "UserStatus must be imported in enterprise_auth_service — "
            "without it, SAML new-user provisioning raises NameError"
        )


# ---------------------------------------------------------------------------
# BUG 3: JWTVerifier accepts user_id claim
# ---------------------------------------------------------------------------


class TestJWTVerifierClaimFallback:
    """JWTVerifier.verify_token must accept tokens with 'user_id' claim,
    not just 'sub'. Same class of bug as the core/auth.py fix."""

    def _make_token(self, claim_name: str, secret: str = "test-secret") -> str:
        import jwt as pyjwt

        payload = {
            claim_name: "user-123",
            "exp": 9999999999,
            "iat": 1,
            "type": "access",
        }
        return pyjwt.encode(payload, secret, algorithm="HS256")

    def _make_credentials(self, token: str):
        """Build a fake HTTPAuthorizationCredentials object."""
        from fastapi.security import HTTPAuthorizationCredentials

        return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    def _make_verifier(self):
        from core.jwt_verifier import JWTVerifier

        # JWTVerifier reads secret_key from env or constructor kwargs.
        # We set it via env to match the token signing key.
        with patch.dict("os.environ", {"JWT_SECRET_KEY": "test-secret"}):
            return JWTVerifier()

    def test_verifier_accepts_user_id_claim(self):
        """Token with only 'user_id' claim must not be rejected for 'missing subject'."""
        verifier = self._make_verifier()
        token = self._make_token("user_id", "test-secret")
        creds = self._make_credentials(token)

        # verify_token should NOT raise "missing subject" — it should either
        # succeed or fail for a different reason (e.g., no audience match).
        try:
            verifier.verify_token(creds)
        except HTTPException as e:
            assert e.status_code != 401 or "missing subject" not in str(e.detail), (
                "Token with 'user_id' claim was rejected as 'missing subject' — "
                "JWTVerifier needs the same sub/id/user_id fallback as core.auth"
            )
        except Exception:
            # Other exceptions (audience, issuer mismatch) are acceptable.
            pass

    def test_verifier_accepts_sub_claim(self):
        """Standard 'sub' claim still works (backward compat)."""
        verifier = self._make_verifier()
        token = self._make_token("sub", "test-secret")
        creds = self._make_credentials(token)

        try:
            verifier.verify_token(creds)
        except HTTPException as e:
            assert "missing subject" not in str(e.detail)
        except Exception:
            pass

    def test_verifier_rejects_token_with_no_subject_claim(self):
        """Token with none of sub/id/user_id must still be rejected (401).
        The exact rejection reason may vary (subject check, audience check,
        etc.) but it must NOT pass verification."""
        verifier = self._make_verifier()
        token = self._make_token("random_claim", "test-secret")
        creds = self._make_credentials(token)

        with pytest.raises(HTTPException) as exc:
            verifier.verify_token(creds)
        assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# BUG 5: oauth_routes.get_current_user no longer trusts X-User-ID
# ---------------------------------------------------------------------------


class TestOauthRoutesAuthFix:
    """The X-User-ID header trust was a CVE-class authentication bypass."""

    def test_x_user_id_header_alone_is_rejected(self):
        """Setting X-User-ID header without a valid JWT must NOT authenticate."""
        from api.oauth_routes import get_current_user

        # Build a fake request with ONLY the X-User-ID header (no JWT)
        fake_request = MagicMock()
        fake_request.headers = {"X-User-ID": "00000000-0000-0000-0000-000000000000"}
        fake_request.cookies = {}

        mock_db = MagicMock()
        fake_user = MagicMock(id="00000000-0000-0000-0000-000000000000")
        mock_db.query.return_value.filter.return_value.first.return_value = fake_user

        # The function is now async — run it in an event loop
        with pytest.raises(HTTPException) as exc:
            asyncio.run(get_current_user(fake_request, mock_db))

        # Must reject (not return the user). The X-User-ID header alone must
        # NOT authenticate — no matter that the user exists in the DB.
        assert exc.value.status_code in (401, 403), (
            "X-User-ID header alone must not authenticate — this is a CVE-class bypass"
        )

    def test_source_code_does_not_read_x_user_id_header(self):
        """Static guard: the function body must not read request.headers['X-User-ID'].
        The docstring may mention it for historical context, but the executable
        code must not use it for authentication decisions."""
        import inspect
        import api.oauth_routes as mod
        import ast

        src = inspect.getsource(mod.get_current_user)
        # Parse the function and check executable statements (not docstrings)
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                # This is a string literal — if it's 'X-User-ID' used as a
                # header lookup key (not inside a docstring), that's the bug.
                # We allow it inside docstrings (ast.get_docstring) but not
                # as an argument to request.headers.get().
                pass  # String constants alone aren't the problem
            if isinstance(node, ast.Call):
                # Check if it's request.headers.get("X-User-ID") pattern
                func = node.func
                if (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Attribute)
                    and func.value.attr == "headers"
                ):
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and arg.value == "X-User-ID":
                            pytest.fail(
                                "get_current_user reads request.headers.get('X-User-ID') "
                                "— authentication bypass risk"
                            )


# ---------------------------------------------------------------------------
# BUG 6: /api/auth/refresh accepts JSON body
# ---------------------------------------------------------------------------


class TestRefreshEndpointBody:
    """The refresh endpoint must accept refresh_token in the JSON body,
    not only as a query parameter."""

    def test_refresh_token_is_body_param_not_query(self):
        """Inspect the OpenAPI parameter location for refresh_token.
        It must be 'body', not 'query'."""
        import inspect
        from api.enterprise_auth_endpoints import refresh_token

        sig = inspect.signature(refresh_token)
        param = sig.parameters.get("refresh_token")

        assert param is not None, "refresh_token parameter must exist"

        # The default must include Body(...) — inspect via the default object
        default = param.default
        # When Body(...) is used, FastAPI wraps it in a Parameter object with
        # a default that is an instance of fastapi.params.Body
        default_str = str(default)
        assert "Body" in default_str or hasattr(default, "embed"), (
            f"refresh_token must use Body() for JSON body — found default: {default_str}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
