"""core/sql_json contract tests (2026-09-13 dialect branch).

``json_field_equals`` used to emit SQLite's ``json_extract`` on EVERY
dialect — PostgreSQL has no ``json_extract``, so the same call site that
fixed the SQLite malformed-JSON crash would fail to EXECUTE on PG. The
branch now renders:

* SQLite: CASE-guarded ``json_extract`` (corrupt rows skipped, statement
  never aborts) — the original live fix, unchanged.
* PostgreSQL: ``json_extract_path_text(col, 'a', 'b')`` (JSONB-native).
* Anything else (or a path the dialect cannot express): raises
  ``NotImplementedError`` instead of emitting SQL that only compiles.
"""

import os
from types import SimpleNamespace

import pytest
from sqlalchemy import (
    Column, Integer, JSON, MetaData, Table, create_engine, select, text,
)
from sqlalchemy.orm import Session

os.environ.setdefault("TESTING", "1")

from core.sql_json import _json_path_keys, is_postgres, is_sqlite, json_field_equals


class _FakeDB:
    """Bind-shaped stub: enough for dialect probing, no engine."""

    def __init__(self, dialect_name):
        self._bind = SimpleNamespace(
            dialect=SimpleNamespace(name=dialect_name))

    def get_bind(self):
        return self._bind


class _BrokenDB:
    def get_bind(self):
        raise RuntimeError("no bind")


# ------------------------------------------------------------ helpers

class TestJsonPathKeys:

    def test_dot_path_to_keys(self):
        assert _json_path_keys("$.a.b") == ["a", "b"]
        assert _json_path_keys("$.metadata") == ["metadata"]
        assert _json_path_keys('$.seg."quoted key"') == ["seg", "quoted key"]

    @pytest.mark.parametrize("path", ["$.items[0]", "$..a", "$.*", "", "$."])
    def test_unsupported_paths_raise(self, path):
        with pytest.raises(NotImplementedError):
            _json_path_keys(path)


# ------------------------------------------------------- dialect probes

class TestDialectProbes:

    def test_is_sqlite_on_real_session(self, db_session):
        assert is_sqlite(db_session) is True
        assert is_postgres(db_session) is False

    def test_probes_on_fakes(self):
        assert is_sqlite(_FakeDB("sqlite")) is True
        assert is_postgres(_FakeDB("postgresql")) is True
        assert is_sqlite(_FakeDB("mysql")) is False
        assert is_postgres(_BrokenDB()) is False


# --------------------------------------------------------- expressions

class TestGeneratedExpressions:

    def test_sqlite_form_keeps_the_case_guard(self, db_session):
        from core.models import AgentExecution

        expr = json_field_equals(
            db_session, AgentExecution.metadata_json, "$.workspace_id", "w")
        sql = str(expr.compile(
            dialect=db_session.get_bind().dialect,
            compile_kwargs={"literal_binds": True}))
        assert "json_valid" in sql and "json_extract" in sql
        assert "CASE" in sql

    def test_postgresql_form_uses_extract_path_text(self):
        from core.models import AgentExecution

        db = _FakeDB("postgresql")
        expr = json_field_equals(
            db, AgentExecution.metadata_json, "$.a.b", "v")
        sql = str(expr.compile(compile_kwargs={"literal_binds": True}))
        assert "json_extract_path_text" in sql
        assert "'a'" in sql and "'b'" in sql
        assert "json_extract(" not in sql  # the SQLite-only function is gone
        assert "json_valid" not in sql      # no SQLite guard on PG

    def test_unknown_dialect_raises_instead_of_emitting(self):
        from core.models import AgentExecution

        with pytest.raises(NotImplementedError, match="mysql"):
            json_field_equals(_FakeDB("mysql"),
                              AgentExecution.metadata_json, "$.a", "v")

    def test_unresolvable_bind_raises(self):
        from core.models import AgentExecution

        with pytest.raises(NotImplementedError):
            json_field_equals(_BrokenDB(),
                              AgentExecution.metadata_json, "$.a", "v")


# ------------------------------------------------- SQLite execution path

class TestSqliteExecution:
    """The original landmine: one corrupt JSON row must not abort the
    statement that reads OTHER rows."""

    def setup_method(self):
        self.engine = create_engine("sqlite://")
        metadata = MetaData()
        self.table = Table(
            "sql_json_probe", metadata,
            Column("id", Integer, primary_key=True),
            Column("meta", JSON))
        metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            conn.execute(self.table.insert().values(id=1, meta={"a": "x"}))
            conn.execute(self.table.insert().values(id=2, meta={"a": "y"}))
            # corrupt row: plain TEXT in a JSON column — possible on SQLite
            conn.execute(text(
                "INSERT INTO sql_json_probe (id, meta) "
                "VALUES (3, 'not-json')"))

    def test_matching_rows_returned_and_corrupt_rows_skipped(self):
        with Session(self.engine) as session:
            stmt = select(self.table.c.id).where(json_field_equals(
                session, self.table.c.meta, "$.a", "x"))
            assert [row[0] for row in session.execute(stmt)] == [1]

    def test_non_matching_value_excludes_everything(self):
        with Session(self.engine) as session:
            stmt = select(self.table.c.id).where(json_field_equals(
                session, self.table.c.meta, "$.a", "z"))
            assert list(session.execute(stmt)) == []
