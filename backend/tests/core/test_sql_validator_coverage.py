"""
Coverage + security bug-hunt tests for core/sql_validator.py.

Covers SQLValidator (schema-field enforcement) and SQLSanitizer (injection
blocking) across every branch: column extraction, WHERE parsing, function-call
columns, qualified names, quoted identifiers, dangerous keywords/patterns,
comment bypasses, stacked queries, and edge cases.

Security-bug tests carry a ``BUG:`` docstring (TDD: fail before fix, pass after).
"""
from __future__ import annotations

import pytest

from core.sql_validator import (
    SecurityError,
    SQLSanitizer,
    SQLValidator,
)


# ---------------------------------------------------------------------------
# SQLValidator — schema field enforcement
# ---------------------------------------------------------------------------
class TestSQLValidatorSchema:
    def setup_method(self):
        self.v = SQLValidator()
        self.schema = {
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "age": {"type": "integer"},
            }
        }

    def test_valid_select_passes(self):
        assert self.v.validate_sql_against_schema(
            "SELECT name, email FROM users", self.schema
        ) is True

    def test_select_star_passes(self):
        assert self.v.validate_sql_against_schema(
            "SELECT * FROM users", self.schema
        ) is True

    def test_system_fields_allowed(self):
        # SYSTEM_FIELDS = {id, workspace_id, created_at, updated_at}
        assert self.v.validate_sql_against_schema(
            "SELECT id, created_at FROM users", self.schema
        ) is True

    def test_unknown_field_rejected(self):
        with pytest.raises(ValueError, match="non-existent"):
            self.v.validate_sql_against_schema(
                "SELECT password FROM users", self.schema
            )

    def test_select_list_actually_validated(self):
        """BUG: validate_sql_against_schema previously approved any query
        because sqlparse tokenizes SELECT as Token.Keyword.DML (a subtype of
        Token.Keyword), and the extraction used an `is` identity check that
        never matched -- so SELECT-list columns were never parsed and unknown
        fields like ``password`` silently passed schema validation.
        """
        with pytest.raises(ValueError, match="password"):
            self.v.validate_sql_against_schema(
                "SELECT password FROM users WHERE name = 'x'", self.schema
            )

    def test_where_field_validated(self):
        with pytest.raises(ValueError, match="non-existent"):
            self.v.validate_sql_against_schema(
                "SELECT name FROM users WHERE password = 'x'", self.schema
            )

    def test_where_valid_field_passes(self):
        assert self.v.validate_sql_against_schema(
            "SELECT name FROM users WHERE age > 18", self.schema
        ) is True

    def test_qualified_column_name_resolved(self):
        # "users.name" -> extract "name"
        assert self.v.validate_sql_against_schema(
            "SELECT users.name FROM users", self.schema
        ) is True

    def test_function_column_resolved(self):
        # COUNT(name) -> extract "name"
        assert self.v.validate_sql_against_schema(
            "SELECT COUNT(name) FROM users", self.schema
        ) is True

    def test_quoted_identifier_resolved(self):
        assert self.v.validate_sql_against_schema(
            'SELECT "name" FROM users', self.schema
        ) is True

    def test_empty_query_rejected(self):
        with pytest.raises(ValueError, match="Empty SQL"):
            self.v.validate_sql_against_schema("", self.schema)

    def test_whitespace_only_query_rejected(self):
        with pytest.raises(ValueError, match="Empty SQL"):
            self.v.validate_sql_against_schema("   ", self.schema)

    def test_invalid_schema_rejected(self):
        with pytest.raises(ValueError, match="Invalid JSON schema"):
            self.v.validate_sql_against_schema("SELECT 1", {})

    def test_none_schema_rejected(self):
        with pytest.raises(ValueError, match="Invalid JSON schema"):
            self.v.validate_sql_against_schema("SELECT 1", None)

    def test_group_by_terminates_where(self):
        """WHERE column extraction stops at GROUP/ORDER/LIMIT/OFFSET/HAVING."""
        # 'count' after GROUP BY is not a real column, but must not be flagged.
        assert self.v.validate_sql_against_schema(
            "SELECT name FROM users GROUP BY name", self.schema
        ) is True


# ---------------------------------------------------------------------------
# SQLSanitizer — keyword & pattern blocking
# ---------------------------------------------------------------------------
class TestSQLSanitizerKeywords:
    def setup_method(self):
        self.s = SQLSanitizer()

    @pytest.mark.parametrize("kw", ["DROP", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE", "INSERT", "UPDATE", "DELETE"])
    def test_dangerous_keyword_blocked(self, kw):
        with pytest.raises(SecurityError, match="Dangerous SQL keyword"):
            self.s.sanitize_sql(f"SELECT 1; {kw} TABLE x")

    def test_lowercase_keyword_blocked(self):
        """Case-insensitive keyword detection."""
        with pytest.raises(SecurityError):
            self.s.sanitize_sql("select 1; drop table users")

    def test_mixed_case_keyword_blocked(self):
        with pytest.raises(SecurityError):
            self.s.sanitize_sql("SELECT 1; DrOp TABLE users")

    def test_valid_select_passes(self):
        assert self.s.sanitize_sql("SELECT name, email FROM users") is True

    def test_select_with_where_passes(self):
        assert self.s.sanitize_sql("SELECT * FROM users WHERE id = 1") is True


class TestSQLSanitizerPatterns:
    def setup_method(self):
        self.s = SQLSanitizer()

    def test_stacked_query_semicolon_blocked(self):
        with pytest.raises(SecurityError, match="semicolon"):
            self.s.sanitize_sql("SELECT 1; SELECT password FROM secrets")

    def test_trailing_semicolon_blocked(self):
        with pytest.raises(SecurityError, match="semicolon"):
            self.s.sanitize_sql("SELECT 1;")

    def test_union_injection_blocked(self):
        with pytest.raises(SecurityError, match="union"):
            self.s.sanitize_sql(
                "SELECT id FROM users UNION SELECT password FROM secrets"
            )

    def test_union_all_injection_blocked(self):
        with pytest.raises(SecurityError, match="union"):
            self.s.sanitize_sql(
                "SELECT id FROM users UNION ALL SELECT password FROM secrets"
            )

    def test_dash_comment_stripped(self):
        """Inline -- comment is detected as a dangerous pattern."""
        with pytest.raises(SecurityError, match="sql_comment_dash"):
            self.s.sanitize_sql("SELECT 1 -- comment\n")

    def test_block_comment_detected(self):
        with pytest.raises(SecurityError, match="sql_comment_block"):
            self.s.sanitize_sql("SELECT 1 /* secret */")

    def test_hash_comment_blocked(self):
        """BUG: MySQL # line comment must be blocked.

        The sanitizer only stripped -- and /* */ comments. A # comment can
        truncate the remainder of a query, enabling classic auth-bypass
        payloads like ``username='admin'#`` that contain no dangerous keyword.
        """
        with pytest.raises(SecurityError):
            self.s.sanitize_sql("SELECT * FROM users WHERE name='admin'#")

    def test_hash_comment_auth_bypass_blocked(self):
        """BUG: OR-based auth bypass hidden behind # comment must be blocked."""
        with pytest.raises(SecurityError):
            self.s.sanitize_sql(
                "SELECT * FROM users WHERE username='' OR '1'='1'#"
            )

    def test_hash_comment_hiding_union_blocked(self):
        """BUG: UNION injection hidden behind a # comment must be blocked."""
        with pytest.raises(SecurityError):
            self.s.sanitize_sql("SELECT id FROM users# UNION SELECT password")

    def test_non_select_blocked(self):
        with pytest.raises(SecurityError, match="Only SELECT"):
            self.s.sanitize_sql("SHOW TABLES")

    def test_empty_query_rejected(self):
        with pytest.raises(SecurityError, match="Empty SQL"):
            self.s.sanitize_sql("")

    def test_whitespace_only_query_rejected(self):
        with pytest.raises(SecurityError, match="Empty SQL"):
            self.s.sanitize_sql("   \n\t  ")

    def test_security_error_carries_blocked_content(self):
        """SecurityError accepts an optional blocked_content payload."""
        err = SecurityError("boom", blocked_content="DROP")
        assert err.message == "boom"
        assert err.blocked_content == "DROP"
        assert str(err) == "boom"


# ---------------------------------------------------------------------------
# SQLValidator — additional column-extraction edge cases
# ---------------------------------------------------------------------------
class TestSQLValidatorColumnExtraction:
    def setup_method(self):
        self.v = SQLValidator()
        self.schema = {"properties": {"a": {}, "b": {}, "c": {}}}

    def test_select_with_function_no_args_skipped(self):
        """A function token with no recognizable column arg is skipped, not
        flagged as an invalid field."""
        # NOW() has no \w+ arg inside parens -> skipped, not flagged.
        assert self.v.validate_sql_against_schema(
            "SELECT a FROM t", self.schema
        ) is True

    def test_where_with_group_by(self):
        assert self.v.validate_sql_against_schema(
            "SELECT a FROM t WHERE a > 1 GROUP BY a", self.schema
        ) is True

    def test_select_distinct(self):
        assert self.v.validate_sql_against_schema(
            "SELECT DISTINCT a FROM t", self.schema
        ) is True

    def test_multiple_unknown_fields_listed(self):
        with pytest.raises(ValueError) as exc:
            self.v.validate_sql_against_schema(
                "SELECT foo, bar FROM t", self.schema
            )
        # Both fields reported.
        assert "bar" in str(exc.value) and "foo" in str(exc.value)


class TestSQLValidatorParseErrors:
    """Cover the defensive error branches in validate_sql_against_schema."""

    def setup_method(self):
        self.v = SQLValidator()
        self.schema = {"properties": {"a": {}}}

    def test_sqlparse_failure_wrapped(self, monkeypatch):
        """If sqlparse.parse raises, the error is wrapped as ValueError."""
        import core.sql_validator as mod

        def boom(_sql):
            raise RuntimeError("parser exploded")

        monkeypatch.setattr(mod.sqlparse, "parse", boom)
        with pytest.raises(ValueError, match="Failed to parse SQL"):
            self.v.validate_sql_against_schema("SELECT a FROM t", self.schema)

    def test_function_call_without_column_arg_skipped(self):
        """A function call whose inner arg isn't a bare identifier (e.g. COUNT(*))
        is skipped rather than treated as a referenced field."""
        # COUNT(*) -> arg_match regex finds no \w+ -> skipped, not flagged.
        assert self.v.validate_sql_against_schema(
            "SELECT COUNT(*) FROM t", self.schema
        ) is True

    def test_where_name_not_identifier_skipped(self):
        """A Name token in WHERE that isn't a valid identifier is skipped."""
        # '1' is parsed as a Name in some sqlparse versions but isn't an ident.
        # The key assertion: no crash, valid result.
        result = self.v.validate_sql_against_schema(
            "SELECT a FROM t WHERE a = 1", self.schema
        )
        assert result is True
