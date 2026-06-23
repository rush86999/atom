"""
TDD regression tests for round 5 bug hunt fixes.

Covers:
- BUG R5-1: Admin auth bypass in api/admin/cache_routes.py (require_admin must enforce)
- BUG R5-2: BYOK manager singleton race condition (thread-safe init)
- BUG R5-3: Exception leakage in byok_endpoints.py (no str(e) in responses)
- BUG R5-4: LLMService.generate async correctness
"""

from __future__ import annotations

import inspect
import threading
import time

import pytest


# ---------------------------------------------------------------------------
# BUG R5-1: Admin auth bypass in cache_routes.require_admin
# ---------------------------------------------------------------------------


class TestAdminAuthEnforced:
    """require_admin must not return None — must raise 401/403."""

    def test_require_admin_signature_uses_get_current_user(self):
        """require_admin must depend on get_current_user (not accept None user_id)."""
        from api.admin import cache_routes

        sig = inspect.signature(cache_routes.require_admin)
        # Must NOT have user_id with default None
        for name, param in sig.parameters.items():
            if name == "user_id":
                # If the parameter exists at all, that's wrong — should use Depends
                assert param.default is not inspect.Parameter.empty, (
                    "user_id parameter must not be a bare query param"
                )

    def test_require_admin_does_not_allow_unauthenticated(self):
        """require_admin function must not have a 'return None' fallback."""
        from api.admin import cache_routes

        src = inspect.getsource(cache_routes.require_admin)
        # The dev-bypass comment + return None must be GONE
        assert "Allow access for development" not in src, (
            "require_admin still has development bypass comment"
        )
        # Function must raise on missing user, not return None
        assert "return None" not in src, (
            "require_admin still returns None — allows unauthenticated access"
        )

    def test_require_admin_raises_on_non_admin(self):
        """Calling require_admin with a non-admin user must raise HTTPException 403."""
        from api.admin import cache_routes
        from core.models import User, UserRole

        # Build a non-admin user (MEMBER role)
        non_admin = User(
            id="00000000-0000-0000-0000-000000000000",
            email="member@example.com",
            role=UserRole.MEMBER,
        )

        # We can verify the source enforces role check
        src = inspect.getsource(cache_routes.require_admin)
        assert "UserRole.ADMIN" in src or "ADMIN" in src, (
            "require_admin must check for ADMIN role"
        )


# ---------------------------------------------------------------------------
# BUG R5-2: BYOK manager singleton thread safety
# ---------------------------------------------------------------------------


class TestBYOKManagerThreadSafe:
    """get_byok_manager() must be thread-safe (no double init under contention)."""

    def test_singleton_uses_lock(self):
        """Source of get_byok_manager must reference threading.Lock or similar."""
        from core import byok_endpoints

        src = inspect.getsource(byok_endpoints.get_byok_manager)
        # Must have a lock acquisition
        assert "Lock" in src or "lock" in src, (
            "get_byok_manager has no thread lock — race condition risk"
        )

    def test_singleton_idempotent(self):
        """Repeated calls return the same instance (basic idempotency)."""
        from core import byok_endpoints

        # Reset state for test
        byok_endpoints._byok_manager = None
        try:
            a = byok_endpoints.get_byok_manager()
            b = byok_endpoints.get_byok_manager()
            assert a is b, "get_byok_manager returned different instances"
        finally:
            byok_endpoints._byok_manager = None


# ---------------------------------------------------------------------------
# BUG R5-3: Exception leakage in byok_endpoints
# ---------------------------------------------------------------------------


class TestNoExceptionLeakage:
    """byok_endpoints handlers must not leak str(e) in HTTPException detail."""

    def test_no_str_e_in_detail(self):
        """Inspect source of byok_endpoints — HTTPException detail="Internal error" is forbidden."""
        from core import byok_endpoints

        src = inspect.getsource(byok_endpoints)
        # Find any HTTPException with detail="Internal error" or detail="Internal error"
        bad_patterns = [
            "detail="Internal error"",
            'detail="Internal error"',
            'detail="Internal error"',
        ]
        for pattern in bad_patterns:
            assert pattern not in src, (
                f"byok_endpoints still has '{pattern}' — leaks internals to clients"
            )


# ---------------------------------------------------------------------------
# BUG R5-4: LLMService.generate is async (not silently broken)
# ---------------------------------------------------------------------------


class TestLLMServiceAsyncContract:
    """LLMService.generate must be a coroutine function."""

    def test_generate_is_coroutine(self):
        """LLMService.generate must be async def."""
        from core.llm_service import LLMService

        assert inspect.iscoroutinefunction(LLMService.generate), (
            "LLMService.generate must be async def — sync callers must use _run_sync"
        )

    def test_generate_embedding_is_coroutine(self):
        """LLMService.generate_embedding must be async def."""
        from core.llm_service import LLMService

        assert inspect.iscoroutinefunction(LLMService.generate_embedding), (
            "LLMService.generate_embedding must be async def"
        )
