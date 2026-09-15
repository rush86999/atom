# -*- coding: utf-8 -*-
"""The app-database NL→SQL envelope (``core/app_db_query.py``).

The agent can ask questions about Atom's OWN operational data ("how many
canvases this week?", "which runs are waiting?") and the planner routes them to
``answer_from_app_db`` — read-only NL→SQL over allowlisted tables.

This module is the security boundary in front of the model's SQL, so it is
tested by PARSE, not by prompt: an allowlist (rejected before the LLM ever sees
a schema), withheld columns, SELECT-only single statements, and a read-only
connection.

Deliberate design decision locked here: there is NO workspace/tenant predicate
injection. This is a single-tenant app and the scope columns are sparsely
populated (53 of 76 canvases carry a NULL workspace_id, measured live
2026-09-15), so `WHERE workspace_id = 'default'` would DROP the operator's own
rows and undercount 76 → 23 rather than isolate anything. Isolation comes from
the table allowlist; scope columns are withheld so the model cannot name them at
all.
"""
import pytest

from core.app_db_query import (
    APP_DB_ALLOWED_TABLES,
    _strip_forbidden_columns,
    validate_app_db_sql,
)


class TestAllowlist:
    def test_operational_tables_are_queryable(self):
        assert validate_app_db_sql("SELECT COUNT(*) FROM canvases") is None
        assert validate_app_db_sql("select name from canvases limit 5") is None

    @pytest.mark.parametrize(
        "table",
        ["users", "integration_tokens", "runtime_settings", "sqlite_master"],
    )
    def test_non_allowlisted_tables_rejected(self, table):
        reason = validate_app_db_sql(f"SELECT * FROM {table}")
        assert reason and "allowlist" in reason

    def test_join_to_a_non_allowlisted_table_rejected(self):
        """A JOIN is the obvious way to smuggle a forbidden table in."""
        reason = validate_app_db_sql(
            "SELECT c.id FROM canvases c JOIN users u ON u.id = c.user_id"
        )
        assert reason and "allowlist" in reason

    def test_allowlist_is_shaped_as_a_review_decision(self):
        """Every entry is an explicit table -> excluded-columns mapping."""
        assert APP_DB_ALLOWED_TABLES, "allowlist must not be empty"
        assert all(
            v is None or isinstance(v, list) for v in APP_DB_ALLOWED_TABLES.values()
        )


class TestWithheldColumns:
    def test_secret_columns_are_never_described(self):
        kept = _strip_forbidden_columns(
            "agent_registry",
            ["id", "name", "api_key", "credential_json", "private_notes", "created_at"],
        )
        assert kept == ["id", "name", "created_at"]

    def test_scope_columns_are_withheld_from_the_schema(self):
        """Not injectable predicates — withheld, because they are unreliable."""
        kept = _strip_forbidden_columns(
            "canvases", ["id", "name", "tenant_id", "workspace_id", "created_at"]
        )
        assert "tenant_id" not in kept and "workspace_id" not in kept
        assert kept == ["id", "name", "created_at"]

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT tenant_id FROM canvases",
            "SELECT workspace_id FROM canvases",
            "SELECT * FROM canvases WHERE workspace_id = 'other'",
            "SELECT api_key FROM agent_registry",
        ],
    )
    def test_naming_a_withheld_column_is_refused(self, sql):
        reason = validate_app_db_sql(sql)
        assert reason and "withheld" in reason

    def test_withholding_scope_columns_keeps_owned_rows_visible(self):
        """The regression this design exists to prevent.

        A NULL workspace_id row is the OPERATOR'S row (single tenant). Any
        predicate on that column drops it, so the honest count is the unfiltered
        one. Verified live: 76 canvases total, 23 with workspace_id='default'.
        """
        sql = "SELECT COUNT(*) FROM canvases"
        assert validate_app_db_sql(sql) is None
        # and the model cannot even express the dropping filter:
        assert validate_app_db_sql(
            "SELECT COUNT(*) FROM canvases WHERE workspace_id = 'default'"
        )


class TestStatementShape:
    def test_select_only(self):
        assert "only SELECT" in (validate_app_db_sql("DELETE FROM canvases") or "")
        assert "only SELECT" in (
            validate_app_db_sql("UPDATE canvases SET name='x'") or ""
        )

    def test_single_statement_only(self):
        reason = validate_app_db_sql("SELECT 1; DROP TABLE canvases")
        assert reason and "multiple statements" in reason

    @pytest.mark.parametrize(
        "verb", ["drop", "insert", "update", "delete", "alter", "attach", "pragma"]
    )
    def test_forbidden_verbs_rejected_even_in_comments(self, verb):
        reason = validate_app_db_sql(f"SELECT * FROM canvases -- {verb}")
        assert reason and "forbidden verb" in reason

    def test_empty_sql_rejected(self):
        assert validate_app_db_sql("") == "empty sql"
        assert validate_app_db_sql("   ") == "empty sql"

    def test_trailing_semicolon_is_tolerated(self):
        assert validate_app_db_sql("SELECT COUNT(*) FROM canvases;") is None


class TestSQLUnwrapping:
    """Providers differ in how strictly they honour a structured-output model.

    ``result.sql`` can hold the raw statement, the whole JSON envelope, a fenced
    block, or a malformed single-quoted dict. Live 2026-09-15 the same question
    was answered correctly and then REFUSED as "only SELECT statements are
    allowed" because the envelope had leaked into the field — the log blamed the
    model's SQL when the model was fine.
    """

    @pytest.mark.parametrize(
        "raw",
        [
            "SELECT COUNT(*) FROM canvases",
            '{"sql": "SELECT COUNT(*) FROM canvases"}',
            '```json\n{"sql": "SELECT COUNT(*) FROM canvases"}\n```',
            "```sql\nSELECT COUNT(*) FROM canvases\n```",
            "{'sql': 'SELECT COUNT(*) FROM canvases'}",
            {"sql": "SELECT COUNT(*) FROM canvases"},
            '{"sql": "SELECT name FROM canvases WHERE name = \'x\'"}',
        ],
    )
    def test_every_shape_yields_valid_sql(self, raw):
        from core.app_db_query import _extract_sql

        sql = _extract_sql(raw)
        assert sql, f"no SQL extracted from {raw!r}"
        assert validate_app_db_sql(sql) is None, f"{sql!r} was rejected"

    @pytest.mark.parametrize("raw", [None, "", "   ", "{}"])
    def test_no_sql_yields_empty(self, raw):
        from core.app_db_query import _extract_sql

        assert _extract_sql(raw) == ""

    def test_unwrapping_cannot_smuggle_a_forbidden_table(self):
        """The envelope is unwrapped BEFORE validation, so the allowlist still
        applies to the recovered statement."""
        from core.app_db_query import _extract_sql

        sql = _extract_sql('{"sql": "SELECT * FROM integration_tokens"}')
        reason = validate_app_db_sql(sql)
        assert reason and "allowlist" in reason
