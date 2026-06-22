"""
TDD regression tests for round 7 bug hunt fixes.

Covers:
- BUG R7-1: Path traversal via unsanitized filename in business_facts upload
- BUG R7-2: SQL injection via workspace_id in schema_aware_sql_generator
- BUG R7-3: SQL injection via workspace_id in multi_entity_sql_generator
- BUG R7-4: LanceDB filter injection via workspace_id/user_id
"""

from __future__ import annotations

import inspect
import os
import re

import pytest


# ---------------------------------------------------------------------------
# BUG R7-1: Path traversal in business_facts upload
# ---------------------------------------------------------------------------


class TestPathTraversalBusinessFacts:
    """Upload endpoint must sanitize filename before writing to disk."""

    def test_filename_sanitized_before_disk_write(self):
        """Source must NOT contain os.path.join(temp_dir, file.filename)."""
        from api.admin import business_facts_routes

        src = inspect.getsource(business_facts_routes)
        # The vulnerable pattern uses file.filename directly in os.path.join
        assert "os.path.join(temp_dir, file.filename)" not in src, (
            "business_facts_routes still writes file.filename to disk unsanitized — "
            "path traversal via '../../etc/passwd' style filenames"
        )

    def test_has_sanitize_filename_helper(self):
        """Module must define or import a filename sanitizer."""
        from api.admin import business_facts_routes

        src = inspect.getsource(business_facts_routes)
        # Either imported or defined inline — either way, must reference sanitization
        assert "sanitize" in src.lower(), (
            "business_facts_routes has no filename sanitization helper"
        )


# ---------------------------------------------------------------------------
# BUG R7-2: SQL injection in schema_aware_sql_generator
# ---------------------------------------------------------------------------


class TestSQLInjectionSchemaAware:
    """workspace_id must be parameterized, not interpolated."""

    def test_workspace_id_not_in_fstring_sql(self):
        """Source must not contain f-string interpolation of workspace_id into SQL."""
        # Read source from file directly (avoids sqlparse import dependency)
        path = "/Users/rushiparikh/projects/atom/backend/core/schema_aware_sql_generator.py"
        with open(path) as f:
            src = f.read()
        # The vulnerable pattern: workspace_id = '{workspace_id}'
        bad_pattern = r"workspace_id\s*=\s*['\"]?\{workspace_id\}"
        matches = re.findall(bad_pattern, src)
        assert not matches, (
            f"schema_aware_sql_generator still interpolates workspace_id into SQL: {matches}"
        )


# ---------------------------------------------------------------------------
# BUG R7-3: SQL injection in multi_entity_sql_generator
# ---------------------------------------------------------------------------


class TestSQLInjectionMultiEntity:
    """workspace_id must be parameterized in multi-entity JOIN queries."""

    def test_workspace_id_not_in_fstring(self):
        path = "/Users/rushiparikh/projects/atom/backend/core/multi_entity_sql_generator.py"
        with open(path) as f:
            src = f.read()
        bad_pattern = r"workspace_id\s*=\s*['\"]?\{self\.workspace_id\}"
        matches = re.findall(bad_pattern, src)
        assert not matches, (
            f"multi_entity_sql_generator still interpolates workspace_id: {matches}"
        )


# ---------------------------------------------------------------------------
# BUG R7-4: LanceDB filter injection
# ---------------------------------------------------------------------------


class TestLanceDBFilterInjection:
    """LanceDB filters must not interpolate workspace_id/user_id."""

    def test_no_string_interpolation_in_filters(self):
        """Source must not build filters with f-string interpolation of ids."""
        from core import lancedb_handler

        src = inspect.getsource(lancedb_handler)
        # The vulnerable patterns:
        # f"workspace_id == '{self.workspace_id}'"
        # f"user_id == '{user_id}'"
        bad_patterns = [
            r"workspace_id\s*==\s*['\"]?\{self\.workspace_id\}",
            r"user_id\s*==\s*['\"]?\{user_id\}",
        ]
        for pat in bad_patterns:
            matches = re.findall(pat, src)
            assert not matches, (
                f"lancedb_handler still interpolates ids into filters: {matches}"
            )
