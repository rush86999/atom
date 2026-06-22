"""
TDD regression tests for round 9 bug hunt fixes.

Covers:
- BUG R9-1: create_admin.py hardcoded password
- BUG R9-2: ensure_admin.py hardcoded password
- BUG R9-3: webhook_security.py hardcoded fallback secret
"""

from __future__ import annotations

import inspect
import os
import re


# ---------------------------------------------------------------------------
# BUG R9-1: create_admin.py hardcoded password
# ---------------------------------------------------------------------------


class TestCreateAdminNoHardcodedPassword:
    """create_admin.py must not hardcode 'securePass123'."""

    def test_no_hardcoded_password(self):
        path = "/Users/rushiparikh/projects/atom/backend/create_admin.py"
        with open(path) as f:
            src = f.read()
        assert "securePass123" not in src, (
            "create_admin.py still has hardcoded 'securePass123' password"
        )

    def test_password_from_env(self):
        path = "/Users/rushiparikh/projects/atom/backend/create_admin.py"
        with open(path) as f:
            src = f.read()
        # Must source password from env var (with no static default)
        assert "ADMIN_PASSWORD" in src and 'os.getenv("ADMIN_PASSWORD"' in src, (
            "create_admin.py should read password from ADMIN_PASSWORD env var"
        )


# ---------------------------------------------------------------------------
# BUG R9-2: ensure_admin.py hardcoded password
# ---------------------------------------------------------------------------


class TestEnsureAdminNoHardcodedPassword:
    """ensure_admin.py must not hardcode 'securePass123'."""

    def test_no_hardcoded_password(self):
        path = "/Users/rushiparikh/projects/atom/backend/ensure_admin.py"
        with open(path) as f:
            src = f.read()
        assert "securePass123" not in src, (
            "ensure_admin.py still has hardcoded 'securePass123' password"
        )


# ---------------------------------------------------------------------------
# BUG R9-3: webhook_security.py hardcoded fallback secret
# ---------------------------------------------------------------------------


class TestWebhookSecurityNoHardcodedSecret:
    """webhook_security.py must not fall back to 'atom-secret-313'."""

    def test_no_hardcoded_secret(self):
        from core import webhook_security

        src = inspect.getsource(webhook_security)
        assert "atom-secret-313" not in src, (
            "webhook_security.py still falls back to hardcoded 'atom-secret-313'"
        )
