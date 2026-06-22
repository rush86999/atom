"""
TDD regression tests for round 13 bug hunt fixes.

Covers:
- BUG R13-1: api/user_management_routes naive datetime comparison
- BUG R13-2: integrations/github_routes naive datetime comparison + DB write
- BUG R13-3: core/productivity/notion_service naive datetime comparison + write
"""

from __future__ import annotations

import ast


def _has_utcnow_call(path: str) -> list:
    """Return list of unsafe datetime.utcnow() call sites.

    Excludes datetime.utcnow().isoformat() — those are payload-string
    builders that don't trigger naive-vs-aware TypeError. Real bugs are
    direct comparisons, DB writes, or arithmetic on datetime.utcnow().
    """
    with open(path) as f:
        src = f.read()
    tree = ast.parse(src)
    matches = []
    for node in ast.walk(tree):
        # Look for the parent call (e.g. `X > datetime.utcnow()` or
        # `foo = datetime.utcnow()`). We detect by finding Call nodes
        # whose func is datetime.utcnow, then checking that the Call
        # is NOT itself the receiver of an `.isoformat()` Attribute call.
        if isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "utcnow"
                and isinstance(func.value, ast.Name)
                and func.value.id == "datetime"
            ):
                # Check whether this Call is the .value of an outer
                # Attribute with attr == "isoformat"
                # (cheap heuristic: search source around lineno for
                # ".utcnow().isoformat()" within a few chars)
                line = src.split("\n")[node.lineno - 1]
                # Find utcnow() on this line, then check what comes after
                # the closing paren
                idx = line.find("datetime.utcnow()")
                if idx >= 0:
                    after = line[idx + len("datetime.utcnow()"):].lstrip()
                    if after.startswith(".isoformat"):
                        continue  # payload string — not a real bug
                matches.append(node.lineno)
    return matches


# ---------------------------------------------------------------------------
# BUG R13-1: user_management_routes naive datetime
# ---------------------------------------------------------------------------


class TestUserManagementNoNaiveDatetime:
    """user_management_routes.py must use timezone-aware datetime in queries."""

    def test_no_utcnow_calls(self):
        path = "/Users/rushiparikh/projects/atom/backend/api/user_management_routes.py"
        matches = _has_utcnow_call(path)
        assert not matches, (
            f"user_management_routes.py still uses datetime.utcnow() at line(s): {matches}"
        )


# ---------------------------------------------------------------------------
# BUG R13-2: github_routes naive datetime
# ---------------------------------------------------------------------------


class TestGithubRoutesNoNaiveDatetime:
    """github_routes.py must use timezone-aware datetime in comparisons/writes."""

    def test_no_utcnow_calls(self):
        path = "/Users/rushiparikh/projects/atom/backend/integrations/github_routes.py"
        matches = _has_utcnow_call(path)
        assert not matches, (
            f"github_routes.py still uses datetime.utcnow() at line(s): {matches}"
        )


# ---------------------------------------------------------------------------
# BUG R13-3: notion_service naive datetime
# ---------------------------------------------------------------------------


class TestNotionServiceNoNaiveDatetime:
    """notion_service.py must use timezone-aware datetime."""

    def test_no_utcnow_calls(self):
        path = "/Users/rushiparikh/projects/atom/backend/core/productivity/notion_service.py"
        matches = _has_utcnow_call(path)
        assert not matches, (
            f"notion_service.py still uses datetime.utcnow() at line(s): {matches}"
        )
