from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import types
import unittest
from collections import namedtuple
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from scripts import initialize_postgres as cli  # noqa: E402


class _Result:
    def __init__(self, *, scalar=None, rows=()):
        self._scalar = scalar
        self._rows = list(rows)

    def scalar_one(self):
        return self._scalar

    def all(self):
        return list(self._rows)


class _Connection:
    def __init__(
        self,
        *,
        label,
        events,
        encoding="UTF8",
        catalog_rows=(),
        current_schema="public",
        has_alembic_version=True,
        revisions=(),
    ):
        self.label = label
        self.events = events
        self.encoding = encoding
        self.catalog_rows = catalog_rows
        self.current_schema = current_schema
        self.has_alembic_version = has_alembic_version
        self.revisions = list(revisions)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, parameters=None):
        return self.exec_driver_sql(str(statement), parameters)

    def exec_driver_sql(self, sql, parameters=None):
        self.events.append((self.label, "sql", sql))
        if "server_encoding" in sql:
            return _Result(scalar=self.encoding)
        if sql.strip() == "SELECT current_schema()":
            return _Result(scalar=self.current_schema)
        if "relname = 'alembic_version'" in sql:
            return _Result(scalar=self.has_alembic_version)
        if "version_num" in sql:
            return _Result(rows=[(revision,) for revision in self.revisions])
        if "attgenerated" in sql:
            return _Result(rows=self.catalog_rows)
        return _Result()

    def commit(self):
        self.events.append((self.label, "commit"))

    def rollback(self):
        self.events.append((self.label, "rollback"))


class _Engine:
    def __init__(self, *, dialect_name, connection):
        self.dialect = SimpleNamespace(name=dialect_name)
        self.connection = connection

    def connect(self):
        return self.connection


class _Metadata:
    def __init__(self, *, events, tables=None):
        self.events = events
        self.tables = (
            {name: object() for name in cli.FTS_INDEXES}
            if tables is None
            else tables
        )

    def create_all(self, conn):
        self.events.append(("metadata", "create_all"))


class _Scripts:
    def __init__(self, heads, *, known=None):
        self._heads = list(heads)
        self._known = list(heads if known is None else known)

    def get_heads(self):
        return list(self._heads)

    def walk_revisions(self):
        return [SimpleNamespace(revision=revision) for revision in self._known]


class _Initializer:
    def __init__(self, *, connection, events, error=None):
        self.connection = connection
        self.events = events
        self.error = error
        self.called = False

    def __call__(self, engine, **callbacks):
        self.called = True
        self.events.append(("initializer", "called"))
        if self.error is not None:
            raise self.error
        callbacks["create_metadata"](self.connection)
        callbacks["verify_extra"](self.connection)
        callbacks["record_expected_heads"](self.connection)
        self.events.append(("initializer", "done"))


class _Stamp:
    def __init__(self, events):
        self.events = events
        self.conn = None
        self.heads = None

    def __call__(self, conn, scripts, heads):
        self.conn = conn
        self.heads = list(heads)
        self.events.append(("stamp", tuple(heads)))


_CatalogRow = namedtuple(
    "_CatalogRow",
    (
        "table generated coltype index method valid ready key_count "
        "key_matches no_predicate"
    ),
)


def _catalog_rows():
    return [
        _CatalogRow(
            table=table,
            generated="s",
            coltype="tsvector",
            index=index,
            method="gin",
            valid=True,
            ready=True,
            key_count=1,
            key_matches=True,
            no_predicate=True,
        )
        for table, index in cli.FTS_INDEXES.items()
    ]


def _replace_table(rows, table, **changes):
    return [
        row._replace(**changes) if row.table == table else row for row in rows
    ]


def _adapters(
    *,
    dialect_name="postgresql",
    encoding="UTF8",
    heads=("20260808_documents_fts", "20260624_reasoning_fts"),
    known=None,
    metadata_tables=None,
    catalog_rows=None,
    initializer_error=None,
    current_schema="public",
    has_alembic_version=True,
    revisions=(),
):
    events = []
    callback_conn = _Connection(
        label="callback",
        events=events,
        encoding=encoding,
        catalog_rows=_catalog_rows() if catalog_rows is None else catalog_rows,
        current_schema=current_schema,
        has_alembic_version=has_alembic_version,
        revisions=revisions,
    )
    engine = _Engine(dialect_name=dialect_name, connection=callback_conn)
    metadata = _Metadata(events=events, tables=metadata_tables)
    scripts = _Scripts(heads, known=known)
    initializer = _Initializer(
        connection=callback_conn, events=events, error=initializer_error
    )
    stamp = _Stamp(events)
    adapters = cli.Adapters(
        engine=engine,
        metadata=metadata,
        scripts=scripts,
        initialize=initializer,
        stamp_heads=stamp,
    )
    return adapters, events, initializer, stamp, metadata, callback_conn


_SUBPROCESS_ALEMBIC_IMPORT = """
import sys
from pathlib import Path

from alembic import __file__ as alembic_file
from alembic.script import ScriptDirectory

backend = Path(sys.argv[1]).resolve()
migration_dir = Path(sys.argv[2]).resolve()
alembic_path = Path(alembic_file).resolve()

if alembic_path.is_relative_to(backend):
    raise SystemExit(f"imported Alembic from the backend tree: {alembic_path}")
if any(migration_dir.glob("*.py")):
    raise SystemExit(
        f"migration directory has a top-level .py marker: {migration_dir}"
    )
scripts = ScriptDirectory(str(migration_dir))
if scripts.get_heads():
    raise SystemExit(f"unexpected migration heads: {scripts.get_heads()!r}")
print(alembic_path)
"""


class InitializePostgresTests(unittest.TestCase):
    def test_success_applies_fts_validates_and_stamps_all_heads(self):
        adapters, events, initializer, stamp, metadata, conn = _adapters()
        output = []

        result = cli.run(adapters, out=output.append)

        self.assertEqual(result, 0)
        self.assertTrue(initializer.called)
        self.assertIs(stamp.conn, conn)
        self.assertEqual(
            stamp.heads,
            ["20260624_reasoning_fts", "20260808_documents_fts"],
        )
        self.assertIn("20260624_reasoning_fts", output[0])
        self.assertIn("20260808_documents_fts", output[0])

        self.assertIn(("metadata", "create_all"), events)
        self.assertLess(
            events.index(("initializer", "called")),
            events.index(("metadata", "create_all")),
        )
        self.assertLess(
            events.index(("callback", "sql", "SHOW server_encoding")),
            events.index(("metadata", "create_all")),
        )
        self.assertLess(
            events.index(("metadata", "create_all")),
            events.index(
                ("stamp", ("20260624_reasoning_fts", "20260808_documents_fts"))
            ),
        )

        statements = [event[2] for event in events if event[1] == "sql"]
        self.assertEqual(
            len([sql for sql in statements if sql.startswith("ALTER TABLE ")]), 3
        )
        self.assertEqual(
            len([sql for sql in statements if sql.startswith("CREATE INDEX ")]), 3
        )
        self.assertTrue(any("attgenerated" in sql for sql in statements))
        self.assertFalse(
            [event for event in events if event[1] in {"commit", "rollback"}]
        )

    def test_refuses_non_postgres_before_any_ddl(self):
        adapters, events, initializer, stamp, _, _ = _adapters(
            dialect_name="sqlite"
        )

        with self.assertRaises(cli.InitializationRefused):
            cli.run(adapters)

        self.assertFalse(initializer.called)
        self.assertIsNone(stamp.heads)
        self.assertNotIn(("metadata", "create_all"), events)
        self.assertFalse([event for event in events if event[1] == "sql"])

    def test_refuses_non_utf8_on_provisioning_connection_before_metadata(self):
        adapters, events, initializer, stamp, _, _ = _adapters(
            encoding="SQL_ASCII"
        )

        with self.assertRaises(cli.InitializationRefused):
            cli.run(adapters)

        self.assertTrue(initializer.called)
        self.assertIsNone(stamp.heads)
        self.assertNotIn(("metadata", "create_all"), events)
        self.assertEqual(
            [
                event[2]
                for event in events
                if event[0] == "callback" and event[1] == "sql"
            ],
            ["SHOW server_encoding"],
        )

    def test_refuses_empty_release_graph_before_any_ddl(self):
        adapters, events, initializer, _, _, _ = _adapters(heads=())

        with self.assertRaises(cli.InitializationRefused):
            cli.run(adapters)

        self.assertFalse(initializer.called)
        self.assertNotIn(("metadata", "create_all"), events)

    def test_refuses_unrevisable_head(self):
        adapters, _, initializer, _, _, _ = _adapters(
            heads=("not-in-graph",), known=()
        )

        with self.assertRaises(cli.InitializationRefused):
            cli.run(adapters)

        self.assertFalse(initializer.called)

    def test_refuses_incomplete_model_metadata_before_initializer(self):
        adapters, _, initializer, _, _, _ = _adapters(
            metadata_tables={"agent_reasoning_steps": object()}
        )

        with self.assertRaises(cli.InitializationRefused):
            cli.run(adapters)

        self.assertFalse(initializer.called)

    def test_propagates_managed_schema_refusal_without_stamping(self):
        adapters, _, _, stamp, _, _ = _adapters(
            initializer_error=RuntimeError("schema 'public' is already managed")
        )

        with self.assertRaises(RuntimeError):
            cli.run(adapters)

        self.assertIsNone(stamp.heads)

    def test_rejects_missing_or_invalid_generated_fts_objects(self):
        rows = _catalog_rows()
        cases = {
            "missing table": rows[1:],
            "not generated": _replace_table(
                rows, "knowledge_documents", generated=" "
            ),
            "not tsvector": _replace_table(
                rows, "ingested_documents", coltype="text"
            ),
            "not gin": _replace_table(
                rows, "agent_reasoning_steps", method="btree"
            ),
            "not valid": _replace_table(
                rows, "agent_reasoning_steps", valid=False
            ),
            "not ready": _replace_table(
                rows, "ingested_documents", ready=False
            ),
            "extra key": _replace_table(
                rows, "knowledge_documents", key_count=2
            ),
            "key mismatch": _replace_table(
                rows, "knowledge_documents", key_matches=False
            ),
            "partial index": _replace_table(
                rows, "knowledge_documents", no_predicate=False
            ),
        }

        for label, catalog_rows in cases.items():
            with self.subTest(label=label):
                adapters, _, _, stamp, _, _ = _adapters(
                    catalog_rows=catalog_rows
                )
                with self.assertRaises(cli.InitializationRefused):
                    cli.run(adapters)
                self.assertIsNone(stamp.heads)

    def test_subprocess_imports_installed_alembic_without_migration_marker(self):
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)

        with tempfile.TemporaryDirectory(
            dir=BACKEND, prefix="alembic-migration-"
        ) as migration_dir:
            Path(migration_dir, "versions").mkdir()
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    _SUBPROCESS_ALEMBIC_IMPORT,
                    str(BACKEND),
                    migration_dir,
                ],
                cwd=BACKEND,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_fts_statements_cover_all_three_tables(self):
        for table, index in cli.FTS_INDEXES.items():
            self.assertTrue(
                any(
                    f"ALTER TABLE {table} " in sql
                    and "GENERATED ALWAYS" in sql
                    and "tsvector" in sql
                    for sql in cli.FTS_STATEMENTS
                )
            )
            self.assertTrue(
                any(
                    index in sql
                    and f"ON {table} USING gin(search_vector)" in sql
                    for sql in cli.FTS_STATEMENTS
                )
            )

    def test_record_heads_uses_alembic_heads_and_never_commits(self):
        events = []
        conn = _Connection(label="stamp", events=events)

        class _Context:
            last = None

            def __init__(self, connection):
                self.connection = connection
                self.stamped = None

            @classmethod
            def configure(cls, connection):
                cls.last = cls(connection)
                return cls.last

            def stamp(self, scripts, revision):
                self.stamped = (scripts, revision)

            def get_current_heads(self):
                return ("20260808_documents_fts", "20260624_reasoning_fts")

        fake_migration = types.ModuleType("alembic.migration")
        fake_migration.MigrationContext = _Context
        fake_alembic = types.ModuleType("alembic")
        fake_alembic.migration = fake_migration
        scripts = _Scripts(("20260624_reasoning_fts", "20260808_documents_fts"))

        with mock.patch.dict(
            sys.modules,
            {"alembic": fake_alembic, "alembic.migration": fake_migration},
        ):
            cli.record_heads(
                conn,
                scripts,
                ["20260624_reasoning_fts", "20260808_documents_fts"],
            )

        self.assertEqual(_Context.last.stamped[1], "heads")
        self.assertFalse([event for event in events if event[1] == "commit"])


class CheckUpgradeTests(unittest.TestCase):
    REVISIONS = ("20260808_documents_fts", "20260624_reasoning_fts")

    def test_accepts_legacy_managed_state_without_bootstrap_marker(self):
        adapters, events, initializer, stamp, _, _ = _adapters(
            revisions=self.REVISIONS
        )
        output = []

        result = cli.check_upgrade(adapters, out=output.append)

        self.assertEqual(result, 0)
        self.assertFalse(initializer.called)
        self.assertIsNone(stamp.heads)
        self.assertNotIn(("metadata", "create_all"), events)
        self.assertIn("20260624_reasoning_fts", output[0])
        self.assertIn("20260808_documents_fts", output[0])

        statements = [event[2] for event in events if event[1] == "sql"]
        self.assertTrue(statements)
        for statement in statements:
            self.assertIn(
                statement.lstrip().split(None, 1)[0].upper(),
                {"SELECT", "SHOW"},
            )
        self.assertFalse(
            [event for event in events if event[1] in {"commit", "rollback"}]
        )

    def test_accepts_matching_explicit_schema(self):
        adapters, _, _, _, _, _ = _adapters(
            revisions=self.REVISIONS, current_schema="tenant"
        )

        result = cli.check_upgrade(
            adapters, schema="tenant", out=lambda _: None
        )

        self.assertEqual(result, 0)

    def test_accepts_legacy_revision_that_is_in_release_graph(self):
        adapters, _, _, _, _, _ = _adapters(
            known=self.REVISIONS + ("20250101_legacy",),
            revisions=("20250101_legacy",),
        )

        result = cli.check_upgrade(adapters, out=lambda _: None)

        self.assertEqual(result, 0)

    def test_refuses_non_postgres_without_any_sql(self):
        adapters, events, _, _, _, _ = _adapters(
            dialect_name="sqlite", revisions=self.REVISIONS
        )

        with self.assertRaises(cli.InitializationRefused):
            cli.check_upgrade(adapters)

        self.assertFalse([event for event in events if event[1] == "sql"])

    def test_refuses_schema_binding_mismatch_before_revision_read(self):
        adapters, events, _, _, _, _ = _adapters(
            revisions=self.REVISIONS, current_schema="public"
        )

        with self.assertRaises(cli.InitializationRefused):
            cli.check_upgrade(adapters, schema="tenant")

        statements = [event[2] for event in events if event[1] == "sql"]
        self.assertFalse(
            [statement for statement in statements if "version_num" in statement]
        )

    def test_refuses_non_utf8_before_table_probe(self):
        adapters, events, _, _, _, _ = _adapters(
            encoding="SQL_ASCII", revisions=self.REVISIONS
        )

        with self.assertRaises(cli.InitializationRefused):
            cli.check_upgrade(adapters)

        statements = [event[2] for event in events if event[1] == "sql"]
        self.assertFalse(
            [statement for statement in statements if "alembic_version" in statement]
        )

    def test_refuses_missing_alembic_version_table(self):
        adapters, _, _, _, _, _ = _adapters(
            has_alembic_version=False, revisions=self.REVISIONS
        )

        with self.assertRaises(cli.InitializationRefused):
            cli.check_upgrade(adapters)

    def test_refuses_marker_only_state_without_version_table(self):
        adapters, _, _, _, _, _ = _adapters(
            has_alembic_version=False, revisions=()
        )

        with self.assertRaises(cli.InitializationRefused):
            cli.check_upgrade(adapters)

    def test_refuses_empty_revision_set(self):
        adapters, _, _, _, _, _ = _adapters(revisions=())

        with self.assertRaises(cli.InitializationRefused):
            cli.check_upgrade(adapters)

    def test_refuses_abbreviated_revision(self):
        adapters, _, _, _, _, _ = _adapters(revisions=("20260624",))

        with self.assertRaises(cli.InitializationRefused):
            cli.check_upgrade(adapters)

    def test_refuses_unknown_revision(self):
        adapters, _, _, _, _, _ = _adapters(
            revisions=("20260101_not_in_graph",)
        )

        with self.assertRaises(cli.InitializationRefused):
            cli.check_upgrade(adapters)

    def test_refuses_duplicate_revision_ids(self):
        adapters, _, _, _, _, _ = _adapters(
            revisions=(self.REVISIONS[0], self.REVISIONS[0])
        )

        with self.assertRaises(cli.InitializationRefused):
            cli.check_upgrade(adapters)

    def test_main_check_upgrade_does_not_initialize(self):
        adapters, _, initializer, stamp, _, _ = _adapters(
            revisions=self.REVISIONS
        )

        result = cli.main(["--check-upgrade"], adapters=adapters)

        self.assertEqual(result, 0)
        self.assertFalse(initializer.called)
        self.assertIsNone(stamp.heads)

    def test_main_check_upgrade_refusal_returns_two(self):
        adapters, _, initializer, _, _, _ = _adapters(revisions=())

        result = cli.main(["--check-upgrade"], adapters=adapters)

        self.assertEqual(result, 2)
        self.assertFalse(initializer.called)

    def test_main_default_remains_fresh_initialization(self):
        adapters, _, initializer, stamp, _, _ = _adapters()

        result = cli.main([], adapters=adapters)

        self.assertEqual(result, 0)
        self.assertTrue(initializer.called)
        self.assertIsNotNone(stamp.heads)


if __name__ == "__main__":
    unittest.main()
