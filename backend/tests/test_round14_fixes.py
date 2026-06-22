"""
TDD regression tests for round 14 bug hunt fixes.

Covers:
- BUG R14-1: login endpoint has no rate limit (brute-force vulnerable)
- BUG R14-2: register endpoint has no rate limit (mass-account vulnerable)
- BUG R14-3: refresh endpoint has no rate limit
- BUG R14-4: byok_endpoints used deprecated @validator
"""

from __future__ import annotations

import inspect


# ---------------------------------------------------------------------------
# BUG R14-1/2/3: Auth endpoints have rate limiting dependencies
# ---------------------------------------------------------------------------


class TestAuthRateLimits:
    """login/register/refresh must have rate limit dependencies."""

    def test_login_has_rate_limit(self):
        from api import enterprise_auth_endpoints
        from core.security.auth_rate_limit import login_rate_limit

        sig = inspect.signature(enterprise_auth_endpoints.login_user)
        deps = [
            p.default
            for p in sig.parameters.values()
            if p.default is not inspect.Parameter.empty
            and hasattr(p.default, "dependency")
        ]
        # login_rate_limit is wrapped by FastAPI's Depends(); the dependency
        # attribute points to the function.
        dep_fns = [getattr(d, "dependency", None) for d in deps]
        assert login_rate_limit in dep_fns, (
            "login_user is missing login_rate_limit dependency"
        )

    def test_register_has_rate_limit(self):
        from api import enterprise_auth_endpoints
        from core.security.auth_rate_limit import register_rate_limit

        sig = inspect.signature(enterprise_auth_endpoints.register_user)
        deps = [
            p.default
            for p in sig.parameters.values()
            if p.default is not inspect.Parameter.empty
            and hasattr(p.default, "dependency")
        ]
        dep_fns = [getattr(d, "dependency", None) for d in deps]
        assert register_rate_limit in dep_fns, (
            "register_user is missing register_rate_limit dependency"
        )

    def test_refresh_has_rate_limit(self):
        from api import enterprise_auth_endpoints
        from core.security.auth_rate_limit import refresh_rate_limit

        sig = inspect.signature(enterprise_auth_endpoints.refresh_token)
        deps = [
            p.default
            for p in sig.parameters.values()
            if p.default is not inspect.Parameter.empty
            and hasattr(p.default, "dependency")
        ]
        dep_fns = [getattr(d, "dependency", None) for d in deps]
        assert refresh_rate_limit in dep_fns, (
            "refresh_token is missing refresh_rate_limit dependency"
        )


class TestAuthRateLimiterBehavior:
    """AuthRateLimiter class enforces sliding-window limits."""

    def test_blocks_after_limit_exceeded(self):
        from core.security.auth_rate_limit import AuthRateLimiter

        class MockRequest:
            class _Client:
                host = "1.2.3.4"
            client = _Client()
            headers = {}

        limiter = AuthRateLimiter(limit=3, window_seconds=60)
        req = MockRequest()

        # First 3 allowed
        results = [limiter.check(req) for _ in range(3)]
        assert all(r[0] for r in results), "first 3 should be allowed"
        # 4th blocked
        allowed, remaining = limiter.check(req)
        assert not allowed, "4th request should be blocked"
        assert remaining == 0


# ---------------------------------------------------------------------------
# BUG R14-4: byok_endpoints used deprecated @validator
# ---------------------------------------------------------------------------


class TestByokValidatorDeprecated:
    """core/byok_endpoints.py must use field_validator, not validator."""

    def test_no_deprecated_validator(self):
        from core import byok_endpoints

        src = inspect.getsource(byok_endpoints)
        # The deprecated import: 'from pydantic import ... validator'
        # The new: 'from pydantic import ... field_validator'
        assert "field_validator" in src, (
            "byok_endpoints should import field_validator from pydantic"
        )
        # @validator decorator (without 'field_' prefix) is the deprecated form
        assert "@validator(" not in src, (
            "byok_endpoints still uses deprecated @validator(...)"
        )
