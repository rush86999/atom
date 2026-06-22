"""
TDD regression tests for round 16 bug hunt fixes.

Covers:
- BUG R16-1: 2FA backup codes hardcoded ("UP-BACKUP-1234-5678")
- BUG R16-2: verify_action_2fa leaks str(e) in error response
- BUG R16-3: 2FA endpoints have no rate limit
"""

from __future__ import annotations

import inspect


# ---------------------------------------------------------------------------
# BUG R16-1: hardcoded backup code
# ---------------------------------------------------------------------------


class TestNoHardcodedBackupCode:
    """auth_2fa_routes must not use a hardcoded backup code."""

    def test_no_hardcoded_backup(self):
        from api import auth_2fa_routes

        src = inspect.getsource(auth_2fa_routes)
        assert "UP-BACKUP-1234-5678" not in src, (
            "auth_2fa_routes.py still uses hardcoded backup code 'UP-BACKUP-1234-5678'"
        )

    def test_generates_random_backup_codes(self):
        from api import auth_2fa_routes

        src = inspect.getsource(auth_2fa_routes.enable_2fa)
        # Must use secrets module or similar to generate backup codes
        assert "secrets." in src or "random" in src, (
            "enable_2fa does not generate random backup codes"
        )


# ---------------------------------------------------------------------------
# BUG R16-2: str(e) leak in verify_action_2fa
# ---------------------------------------------------------------------------


class TestVerifyActionNoStrLeak:
    """verify_action_2fa must not leak str(e) to client."""

    def test_no_str_e_in_error(self):
        from api import auth_2fa_routes

        src = inspect.getsource(auth_2fa_routes.verify_action_2fa)
        # Forbidden: f"...{str(e)}" or str(e) in error response
        assert "{str(e)}" not in src and "f\"...{e}\"" not in src, (
            "verify_action_2fa still leaks str(e) to client"
        )


# ---------------------------------------------------------------------------
# BUG R16-3: rate limit on 2FA endpoints
# ---------------------------------------------------------------------------


class Test2FARateLimit:
    """verify-action/enable/disable should have rate limits (anti-brute-force)."""

    def test_verify_action_has_rate_limit(self):
        from api import auth_2fa_routes

        sig = inspect.signature(auth_2fa_routes.verify_action_2fa)
        deps = [
            p.default
            for p in sig.parameters.values()
            if p.default is not inspect.Parameter.empty
            and hasattr(p.default, "dependency")
        ]
        dep_names = [
            getattr(getattr(d, "dependency", None), "__name__", "") for d in deps
        ]
        assert any("rate_limit" in n for n in dep_names), (
            f"verify_action_2fa has no rate limit; deps: {dep_names}"
        )
