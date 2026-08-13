# -*- coding: utf-8 -*-
"""Coverage wave 88 — core/sql_validator (110 stmts, never wave-tested).

SQLValidator:
- validate_sql_against_schema: empty/whitespace query, schema w/o properties,
  valid SELECT list + WHERE, system fields, `*`, quoted/backticked/qualified
  identifiers, aggregate fn args (COUNT(id)), invalid SELECT-field and
  invalid WHERE-field rejection, parse-failure ValueError, ORDER BY / GROUP BY
  column references (REGRESSION: previously unvalidated — non-existent fields
  in ORDER BY / GROUP BY were silently approved).
- SQLSanitizer (injection allowlist): empty query, every DANGEROUS_KEYWORDS
  member (DROP/TRUNCATE/ALTER/CREATE/GRANT/REVOKE/INSERT/UPDATE/DELETE),
  stacked-statement semicolon, -- / # / /* */ comments, UNION SELECT, non-SELECT
  statements, and the REAL-BUG regressions this wave fixes: `INTO OUTFILE` /
  `INTO DUMPFILE` server-side file write, `LOAD_FILE(...)` server-side file
  read, and SQLite/Postgres metadata-schema probing (`sqlite_master`,
  `information_schema`, `pg_catalog`) — all were previously ALLOWED.

Fully mocked / no network / no LLM. sqlparse only.
"""
import pytest
import sqlparse

from core.sql_validator import (
    SQLValidator,
    SQLSanitizer,
    SecurityError,
)


VALID_SCHEMA = {
    "properties": {
        "id": {"type": "integer"},
        "name": {"type": "string"},
        "email": {"type": "string"},
        "status": {"type": "string"},
    }
}


class TestSQLValidatorBasics:
    def test_empty_query_raises(self):
        with pytest.raises(ValueError, match="Empty SQL query"):
            SQLValidator().validate_sql_against_schema("", VALID_SCHEMA)

    def test_whitespace_query_raises(self):
        with pytest.raises(ValueError, match="Empty SQL query"):
            SQLValidator().validate_sql_against_schema("   \n\t ", VALID_SCHEMA)

    def test_schema_without_properties_raises(self):
        with pytest.raises(ValueError, match="missing 'properties'"):
            SQLValidator().validate_sql_against_schema("SELECT id FROM t", {"type": "object"})

    def test_valid_select_list_and_where(self):
        v = SQLValidator()
        assert v.validate_sql_against_schema(
            "SELECT id, name FROM users WHERE status = 'active'", VALID_SCHEMA
        ) is True

    def test_valid_all_fields(self):
        v = SQLValidator()
        assert v.validate_sql_against_schema(
            "SELECT id, name, email, status FROM users WHERE email LIKE '%@x.com'",
            VALID_SCHEMA,
        ) is True

    def test_invalid_select_field_rejected(self):
        v = SQLValidator()
        with pytest.raises(ValueError, match="non-existent fields: secret"):
            v.validate_sql_against_schema("SELECT id, secret FROM users", VALID_SCHEMA)

    def test_invalid_where_field_rejected(self):
        v = SQLValidator()
        with pytest.raises(ValueError, match="non-existent fields: nope"):
            v.validate_sql_against_schema("SELECT id FROM users WHERE nope = 1", VALID_SCHEMA)

    def test_multiple_invalid_fields_sorted(self):
        v = SQLValidator()
        with pytest.raises(ValueError, match="non-existent fields: b_field, z_field"):
            v.validate_sql_against_schema(
                "SELECT id, z_field FROM users WHERE b_field = 1", VALID_SCHEMA
            )

    def test_system_fields_allowed(self):
        v = SQLValidator()
        assert v.validate_sql_against_schema(
            "SELECT id, workspace_id, created_at, updated_at FROM users", VALID_SCHEMA
        ) is True

    def test_star_select_allowed(self):
        v = SQLValidator()
        assert v.validate_sql_against_schema("SELECT * FROM users WHERE status = 'x'", VALID_SCHEMA) is True

    def test_table_qualified_columns(self):
        v = SQLValidator()
        assert v.validate_sql_against_schema(
            "SELECT u.id, u.email FROM users u WHERE u.status = 'x'", VALID_SCHEMA
        ) is True

    def test_quoted_and_backticked_identifiers(self):
        v = SQLValidator()
        assert v.validate_sql_against_schema(
            'SELECT "id", `name` FROM users', VALID_SCHEMA
        ) is True

    def test_aggregate_function_argument_validated(self):
        v = SQLValidator()
        assert v.validate_sql_against_schema(
            "SELECT COUNT(id) FROM users WHERE status = 'x'", VALID_SCHEMA
        ) is True

    def test_aggregate_with_unknown_column_rejected(self):
        v = SQLValidator()
        with pytest.raises(ValueError, match="non-existent fields: bogus"):
            v.validate_sql_against_schema("SELECT COUNT(bogus) FROM users", VALID_SCHEMA)

    def test_count_star_skipped(self):
        v = SQLValidator()
        assert v.validate_sql_against_schema("SELECT COUNT(*) FROM users", VALID_SCHEMA) is True

    def test_where_clause_terminated_by_limit(self):
        v = SQLValidator()
        assert v.validate_sql_against_schema(
            "SELECT id FROM users WHERE status = 'x' LIMIT 10", VALID_SCHEMA
        ) is True

    def test_where_clause_terminated_by_having(self):
        v = SQLValidator()
        assert v.validate_sql_against_schema(
            "SELECT status FROM users WHERE status = 'x' GROUP BY status HAVING COUNT(*) > 1",
            VALID_SCHEMA,
        ) is True

    def test_parse_failure_raises_value_error(self, monkeypatch):
        v = SQLValidator()

        def _boom(*a, **k):
            raise RuntimeError("parser exploded")

        monkeypatch.setattr(sqlparse, "parse", _boom)
        with pytest.raises(ValueError, match="Failed to parse SQL"):
            v.validate_sql_against_schema("SELECT id FROM users", VALID_SCHEMA)


class TestSQLValidatorOrderGroupBy:
    """REGRESSION (real bug, fixed this wave): ORDER BY / GROUP BY column
    references were never extracted, so queries referencing non-existent
    fields in those clauses were silently approved."""

    def test_order_by_known_column_allowed(self):
        v = SQLValidator()
        assert v.validate_sql_against_schema(
            "SELECT id FROM users ORDER BY name", VALID_SCHEMA
        ) is True

    def test_order_by_unknown_column_rejected(self):
        v = SQLValidator()
        with pytest.raises(ValueError, match="non-existent fields: secret_col"):
            v.validate_sql_against_schema(
                "SELECT id FROM users ORDER BY secret_col", VALID_SCHEMA
            )

    def test_order_by_multiple_columns(self):
        v = SQLValidator()
        with pytest.raises(ValueError, match="non-existent fields: ghost"):
            v.validate_sql_against_schema(
                "SELECT id FROM users ORDER BY name ASC, ghost DESC", VALID_SCHEMA
            )

    def test_group_by_unknown_column_rejected(self):
        v = SQLValidator()
        with pytest.raises(ValueError, match="non-existent fields: secret_col"):
            v.validate_sql_against_schema(
                "SELECT status FROM users GROUP BY secret_col", VALID_SCHEMA
            )

    def test_group_by_known_column_allowed(self):
        v = SQLValidator()
        assert v.validate_sql_against_schema(
            "SELECT status FROM users GROUP BY status", VALID_SCHEMA
        ) is True

    def test_order_by_ordinal_position_not_a_field(self):
        v = SQLValidator()
        assert v.validate_sql_against_schema(
            "SELECT id FROM users ORDER BY 1", VALID_SCHEMA
        ) is True

    def test_order_by_clause_closed_by_limit(self):
        v = SQLValidator()
        assert v.validate_sql_against_schema(
            "SELECT id FROM users ORDER BY name LIMIT 5", VALID_SCHEMA
        ) is True

    def test_order_by_clause_closed_by_semicolon(self):
        v = SQLValidator()
        assert v.validate_sql_against_schema(
            "SELECT id FROM users ORDER BY name;", VALID_SCHEMA
        ) is True


class TestSQLSanitizerBasics:
    def test_empty_query_raises(self):
        with pytest.raises(SecurityError, match="Empty SQL query"):
            SQLSanitizer().sanitize_sql("")

    def test_whitespace_query_raises(self):
        with pytest.raises(SecurityError, match="Empty SQL query"):
            SQLSanitizer().sanitize_sql("   \n ")

    @pytest.mark.parametrize("keyword", [
        "DROP", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE",
        "INSERT", "UPDATE", "DELETE",
    ])
    def test_dangerous_keywords_blocked(self, keyword):
        with pytest.raises(SecurityError, match=f"Dangerous SQL keyword detected: {keyword}"):
            SQLSanitizer().sanitize_sql(f"SELECT 1; {keyword} TABLE users")

    def test_keywords_blocked_case_insensitively(self):
        with pytest.raises(SecurityError, match="DROP"):
            SQLSanitizer().sanitize_sql("select 1; drop table users")

    def test_semicolon_stacked_statements_blocked(self):
        with pytest.raises(SecurityError, match="sql_injection_semicolon"):
            SQLSanitizer().sanitize_sql("SELECT 1; SELECT password FROM secrets")

    def test_trailing_semicolon_blocked(self):
        with pytest.raises(SecurityError, match="sql_injection_semicolon"):
            SQLSanitizer().sanitize_sql("SELECT * FROM users;")

    @pytest.mark.parametrize("comment", [
        "SELECT 1 -- comment",
        "SELECT 1 # comment",
        "SELECT 1 /* comment */",
    ])
    def test_comments_blocked(self, comment):
        with pytest.raises(SecurityError, match="sql_comment"):
            SQLSanitizer().sanitize_sql(comment)

    def test_union_select_blocked(self):
        with pytest.raises(SecurityError, match="union_based_injection"):
            SQLSanitizer().sanitize_sql("SELECT id FROM users UNION SELECT password FROM admin")

    def test_union_all_select_blocked(self):
        with pytest.raises(SecurityError, match="union_based_injection"):
            SQLSanitizer().sanitize_sql("SELECT id FROM users UNION ALL SELECT password FROM admin")

    def test_non_select_statement_blocked(self):
        with pytest.raises(SecurityError, match="Only SELECT queries"):
            SQLSanitizer().sanitize_sql("SHOW TABLES")

    def test_explain_blocked(self):
        with pytest.raises(SecurityError, match="Only SELECT queries"):
            SQLSanitizer().sanitize_sql("EXPLAIN SELECT * FROM users")

    def test_valid_select_allowed(self):
        assert SQLSanitizer().sanitize_sql(
            "SELECT id, name FROM users WHERE status = 'active'"
        ) is True

    def test_valid_select_with_quotes_and_backticks(self):
        assert SQLSanitizer().sanitize_sql("SELECT `name` FROM users WHERE id = 5") is True

    def test_lowercase_select_allowed(self):
        assert SQLSanitizer().sanitize_sql("select * from users where id = 1") is True

    def test_security_error_carries_blocked_content(self):
        try:
            SQLSanitizer().sanitize_sql("SELECT 1;")
        except SecurityError as e:
            assert e.message == "Dangerous SQL pattern detected: sql_injection_semicolon"
            assert e.blocked_content is None


class TestSQLSanitizerInjectionAllowances:
    """REGRESSION (real bugs, fixed this wave): server-side file write/read
    and metadata-schema probing previously passed sanitization."""

    def test_into_outfile_blocked(self):
        with pytest.raises(SecurityError, match="into_outfile"):
            SQLSanitizer().sanitize_sql("SELECT * FROM users INTO OUTFILE '/tmp/evil.csv'")

    def test_into_dumpfile_blocked(self):
        with pytest.raises(SecurityError, match="into_outfile"):
            SQLSanitizer().sanitize_sql("SELECT * FROM users INTO DUMPFILE '/tmp/evil'")

    def test_into_outfile_case_insensitive(self):
        with pytest.raises(SecurityError, match="into_outfile"):
            SQLSanitizer().sanitize_sql("select * from t into outfile '/tmp/x'")

    def test_load_file_blocked(self):
        with pytest.raises(SecurityError, match="load_file"):
            SQLSanitizer().sanitize_sql("SELECT LOAD_FILE('/etc/passwd')")

    def test_load_file_case_insensitive(self):
        with pytest.raises(SecurityError, match="load_file"):
            SQLSanitizer().sanitize_sql("SELECT load_file('/etc/shadow')")

    def test_sqlite_master_probe_blocked(self):
        with pytest.raises(SecurityError, match="sqlite_meta_table"):
            SQLSanitizer().sanitize_sql("SELECT name FROM sqlite_master")

    def test_sqlite_schema_probe_blocked(self):
        with pytest.raises(SecurityError, match="sqlite_meta_table"):
            SQLSanitizer().sanitize_sql("SELECT sql FROM sqlite_schema")

    def test_information_schema_probe_blocked(self):
        with pytest.raises(SecurityError, match="sql_meta_schema"):
            SQLSanitizer().sanitize_sql("SELECT table_name FROM information_schema.tables")

    def test_pg_catalog_probe_blocked(self):
        with pytest.raises(SecurityError, match="sql_meta_schema"):
            SQLSanitizer().sanitize_sql("SELECT relname FROM pg_catalog.pg_tables")

    def test_legit_like_named_columns_still_allowed(self):
        # \b boundaries must not catch names that merely embed 'mysql'
        assert SQLSanitizer().sanitize_sql(
            "SELECT mysql_product_id FROM inventory WHERE qty > 0"
        ) is True
