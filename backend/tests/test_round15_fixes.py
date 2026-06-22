"""
TDD regression tests for round 15 bug hunt fixes.

Covers:
- BUG R15-1: email_verification /verify endpoint leaks user existence (different errors)
- BUG R15-2: email_verification uses naive datetime comparison
- BUG R15-3: email_verification /verify endpoint has no rate limit
"""

from __future__ import annotations

import ast
import inspect


def _ast_calls(path: str, func_name: str) -> list:
    """Find call sites of `func_name(` in file via AST."""
    with open(path) as f:
        src = f.read()
    tree = ast.parse(src)
    matches = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == func_name:
                matches.append(node.lineno)
            elif isinstance(func, ast.Name) and func.id == func_name:
                matches.append(node.lineno)
    return matches


# ---------------------------------------------------------------------------
# BUG R15-1: /verify endpoint must NOT raise not_found_error for unknown email
# ---------------------------------------------------------------------------


class TestVerifyNoUserEnumeration:
    """/verify must return same error for unknown user and invalid code."""

    def test_verify_does_not_raise_not_found(self):
        """verify_email must not call router.not_found_error — that leaks
        which emails are registered."""
        from api import email_verification_routes

        src = inspect.getsource(email_verification_routes.verify_email)
        assert "not_found_error" not in src, (
            "verify_email raises not_found_error on missing user — "
            "this leaks which emails are registered (user enumeration)"
        )


# ---------------------------------------------------------------------------
# BUG R15-2: email_verification uses naive datetime
# ---------------------------------------------------------------------------


class TestEmailVerificationNoNaiveDatetime:
    """email_verification_routes.py must use timezone-aware datetime."""

    def test_no_utcnow_in_comparisons_or_writes(self):
        path = "/Users/rushiparikh/projects/atom/backend/api/email_verification_routes.py"
        # Allow .isoformat() payload strings; flag direct utcnow calls.
        with open(path) as f:
            src = f.read()
        tree = ast.parse(src)
        bad_lines = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "utcnow"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "datetime"
                ):
                    line = src.split("\n")[node.lineno - 1]
                    idx = line.find("datetime.utcnow()")
                    after = line[idx + 16:].lstrip() if idx >= 0 else ""
                    if not after.startswith(".isoformat"):
                        bad_lines.append(node.lineno)
        assert not bad_lines, (
            f"email_verification_routes.py uses naive datetime.utcnow() at line(s): {bad_lines}"
        )


# ---------------------------------------------------------------------------
# BUG R15-3: /verify endpoint must have rate limit
# ---------------------------------------------------------------------------


class TestVerifyRateLimit:
    """/verify endpoint must depend on a rate limit function."""

    def test_verify_has_rate_limit(self):
        from api import email_verification_routes

        sig = inspect.signature(email_verification_routes.verify_email)
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
            f"verify_email has no rate limit dependency; deps: {dep_names}"
        )
