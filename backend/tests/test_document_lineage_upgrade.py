"""Existing-database upgrade for ``dataset_entries.source_document_id``.

``Base.metadata.create_all`` is not an upgrade path: it creates missing
tables but never ALTERs an existing one. The lineage column therefore reached
SQLite files only through ``core.sqlite_schema_repair`` and PostgreSQL not at
all, because PostgreSQL is owned by Alembic. This contract exercises the real
migration against a scratch legacy-schema SQLite database:

* the old ``dataset_entries`` shape upgrades to the current ORM shape;
* every pre-existing row, the version unique constraint and the old indexes
  are preserved (the upgrade is a nullable ADD COLUMN + one index);
* legacy lineage stays NULL — no filename/content-address backfill;
* re-running the migration's ``upgrade()`` on an upgraded, partial, current
  ``create_all``, or absent-table database is a safe no-op/repair;
* downgrade removes only what this revision added.

PostgreSQL is covered **statically only**: the column DDL and index are
compiled with the PostgreSQL dialect, and the migration source is checked for
guards and absence of data rewrites. No PostgreSQL server or connection is
opened here — the repository's e2e PostgreSQL fixture is a shared
``localhost:5433`` database, not a scratch harness this test may own, and no
claim about a live PG upgrade is made.

Scratch-only: every database lives under ``tmp_path``; no live development
database is opened.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateColumn, CreateIndex

BACKEND_DIR = Path(__file__).resolve().parents[1]
MIGRATION_FILE = (
    BACKEND_DIR / "alembic/versions/20261117_dataset_entry_source_document.py"
)
PRE_REVISION = "20261116_action_autonomy_rules"
MIGRATION_REVISION = "20261117_dataset_entry_lineage"
TABLE = "dataset_entries"
COLUMN = "source_document_id"
INDEX = "ix_dataset_entries_source_document_id"
FILE_LOOKUP_INDEX = "ix_dataset_entries_file_lookup"

# Every column the table had before lineage was added.
OLD_COLUMNS = (
    "id",
    "workspace_id",
    "tenant_id",
    "created_by",
    "source_kind",
    "source",
    "external_id",
    "file_name",
    "content_hash",
    "entity_name",
    "dataset_name",
    "parquet_path",
    "row_count",
    "column_count",
    "columns_json",
    "source_modified_at",
    "ingested_at",
    "status",
    "superseded_by",
)

LEGACY_ROWS = (
    {
        "id": "entry-active",
        "workspace_id": "ws-1",
        "tenant_id": "tenant-1",
        "created_by": "user-1",
        "source_kind": "file",
        "source": "upload",
        "external_id": "sha1-of-source-bytes",
        "file_name": "budget.csv",
        "content_hash": "hash-active",
        "entity_name": "Sheet1",
        "dataset_name": "budget_sheet1",
        "parquet_path": "/scratch/budget.parquet",
        "row_count": 3,
        "column_count": 2,
        "columns_json": '["item", "amount"]',
        "source_modified_at": "2026-11-01 10:00:00",
        "ingested_at": "2026-11-01 10:00:01",
        "status": "active",
        "superseded_by": None,
    },
    {
        "id": "entry-superseded",
        "workspace_id": "ws-1",
        "tenant_id": "tenant-1",
        "created_by": "user-1",
        "source_kind": "file",
        "source": "upload",
        "external_id": "sha1-of-older-bytes",
        "file_name": "budget.csv",
        "content_hash": "hash-superseded",
        "entity_name": "Sheet1",
        "dataset_name": "budget_sheet1",
        "parquet_path": "/scratch/older-budget.parquet",
        "row_count": 2,
        "column_count": 2,
        "columns_json": '["item", "amount"]',
        "source_modified_at": "2026-10-01 10:00:00",
        "ingested_at": "2026-10-01 10:00:01",
        "status": "superseded",
        "superseded_by": "entry-active",
    },
)

_INSERT_ROW = sa.text(
    "INSERT INTO dataset_entries ("
    + ", ".join(OLD_COLUMNS)
    + ") VALUES ("
    + ", ".join(f":{name}" for name in OLD_COLUMNS)
    + ")"
)


# ---------------------------------------------------------------------------
# Alembic import hygiene
# ---------------------------------------------------------------------------
# ``backend/alembic`` is the repository's migration-script directory and also
# shadows the installed ``alembic`` package whenever ``backend`` is on
# ``sys.path``. Import the runtime while that directory is off the path, then
# restore backend for ``core.*`` imports.
def _import_alembic_runtime():
    backend_str = str(BACKEND_DIR)
    shadowed = [
        name for name, module in list(sys.modules.items())
        if (name == "alembic" or name.startswith("alembic."))
        and getattr(module, "__file__", None)
        and backend_str in str(Path(module.__file__).resolve())
    ]
    for name in shadowed:
        del sys.modules[name]
    saved_path = list(sys.path)
    sys.path = [
        entry for entry in sys.path
        if entry and Path(entry).resolve() != BACKEND_DIR
        and Path(entry).name != "backend"
    ]
    try:
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
    finally:
        sys.path = saved_path
    return MigrationContext, Operations


def _load_migration():
    # Import the installed Alembic runtime first: the migration module does
    # ``from alembic import op`` and must not resolve the script directory.
    _import_alembic_runtime()
    spec = importlib.util.spec_from_file_location(
        "dataset_entry_lineage_migration", MIGRATION_FILE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _direct_upgrade(db_path: Path, calls: int = 2) -> None:
    """Run the migration's own ``upgrade()`` (not the CLI version stamp)."""
    migration = _load_migration()
    MigrationContext, Operations = _import_alembic_runtime()
    engine = sa.create_engine(f"sqlite:///{db_path}")
    try:
        with engine.begin() as connection:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                for _ in range(calls):
                    migration.upgrade()
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Legacy and fresh scratch schemas
# ---------------------------------------------------------------------------
def _build_pre_migration_database(db_path: Path) -> None:
    # SQLAlchemy's SQLite reflection parses the CREATE TABLE text for a
    # table-level UNIQUE constraint; keep it on one line exactly like
    # ``create_all`` emits it. Splitting the column list across lines makes
    # the legacy shape unrepresentative and reflection could miss the
    # constraint.
    unique_constraint = (
        "CONSTRAINT uq_dataset_entries_version UNIQUE "
        "(source_kind, source, external_id, content_hash, entity_name)"
    )
    engine = sa.create_engine(f"sqlite:///{db_path}")
    try:
        with engine.begin() as connection:
            connection.execute(sa.text(f"""
                CREATE TABLE {TABLE} (
                    id VARCHAR NOT NULL PRIMARY KEY,
                    workspace_id VARCHAR,
                    tenant_id VARCHAR,
                    created_by VARCHAR,
                    source_kind VARCHAR NOT NULL,
                    source VARCHAR NOT NULL,
                    external_id VARCHAR NOT NULL,
                    file_name VARCHAR,
                    content_hash VARCHAR NOT NULL,
                    entity_name VARCHAR NOT NULL,
                    dataset_name VARCHAR NOT NULL,
                    parquet_path VARCHAR NOT NULL,
                    row_count INTEGER,
                    column_count INTEGER,
                    columns_json JSON,
                    source_modified_at DATETIME,
                    ingested_at DATETIME,
                    status VARCHAR NOT NULL,
                    superseded_by VARCHAR,
                    {unique_constraint}
                )
            """))
            connection.execute(sa.text(
                f"CREATE INDEX ix_dataset_entries_workspace_id "
                f"ON {TABLE} (workspace_id)"
            ))
            connection.execute(sa.text(
                f"CREATE INDEX ix_dataset_entries_external_id "
                f"ON {TABLE} (external_id)"
            ))
            connection.execute(sa.text(
                f"CREATE INDEX {FILE_LOOKUP_INDEX} "
                f"ON {TABLE} (source, external_id, status)"
            ))
            connection.execute(sa.text(
                "CREATE TABLE alembic_version "
                "(version_num VARCHAR(32) NOT NULL)"
            ))
            connection.execute(
                sa.text("INSERT INTO alembic_version (version_num) "
                        "VALUES (:revision)"),
                {"revision": PRE_REVISION},
            )
            for row in LEGACY_ROWS:
                connection.execute(_INSERT_ROW, row)
    finally:
        engine.dispose()


def _build_current_schema_database(db_path: Path) -> None:
    """Simulate a database created by ``Base.metadata.create_all``."""
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    from core.database import Base

    engine = sa.create_engine(f"sqlite:///{db_path}")
    try:
        Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables[TABLE]])
        with engine.begin() as connection:
            row = dict(LEGACY_ROWS[0])
            row["source_document_id"] = "doc-already-linked"
            connection.execute(_INSERT_ROW, row)
    finally:
        engine.dispose()


def _run_alembic(tmp_path: Path, db_path: Path, *arguments: str) -> None:
    alembic_bin = (
        shutil.which("alembic")
        or str(Path(sys.executable).with_name("alembic"))
    )
    if not Path(alembic_bin).exists():
        pytest.skip("alembic console script is not available on PATH")
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{db_path}"
    environment["TESTING"] = "0"
    environment["PYTHON_DOTENV_DISABLED"] = "1"
    environment["SECRET_KEY"] = "ci-test-secret-key"
    environment["ENVIRONMENT"] = "development"
    environment.pop("PYTHONPATH", None)
    # Run outside backend/ so the local ``backend/alembic`` package cannot
    # shadow the installed Alembic package.
    result = subprocess.run(
        [alembic_bin, "-c", str(BACKEND_DIR / "alembic.ini"), *arguments],
        cwd=str(tmp_path),
        env=environment,
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert result.returncode == 0, result.stderr


def _snapshot(db_path: Path) -> list[dict]:
    engine = sa.create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            rows = connection.execute(sa.text(
                "SELECT " + ", ".join(OLD_COLUMNS)
                + f" FROM {TABLE} ORDER BY id"
            )).mappings().all()
            return [dict(row) for row in rows]
    finally:
        engine.dispose()


def _columns(db_path: Path) -> dict:
    engine = sa.create_engine(f"sqlite:///{db_path}")
    try:
        return {
            column["name"]: column
            for column in sa.inspect(engine).get_columns(TABLE)
        }
    finally:
        engine.dispose()


def _indexes(db_path: Path) -> dict:
    engine = sa.create_engine(f"sqlite:///{db_path}")
    try:
        return {
            index["name"]: index
            for index in sa.inspect(engine).get_indexes(TABLE)
        }
    finally:
        engine.dispose()


def _unique_constraints(db_path: Path) -> dict:
    engine = sa.create_engine(f"sqlite:///{db_path}")
    try:
        return {
            constraint["name"]: constraint["column_names"]
            for constraint in sa.inspect(engine).get_unique_constraints(TABLE)
        }
    finally:
        engine.dispose()


def _assert_unique_constraint_enforced(db_path: Path) -> None:
    engine = sa.create_engine(f"sqlite:///{db_path}")
    try:
        duplicate = dict(LEGACY_ROWS[0])
        duplicate["id"] = "entry-duplicate"
        duplicate["superseded_by"] = None
        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as connection:
                connection.execute(_INSERT_ROW, duplicate)
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Real scratch-SQLite upgrade
# ---------------------------------------------------------------------------
def test_existing_table_upgrade_adds_lineage_and_preserves_rows(tmp_path):
    db_path = tmp_path / "legacy-dataset-entries.db"
    _build_pre_migration_database(db_path)
    before = _snapshot(db_path)

    _run_alembic(tmp_path, db_path, "upgrade", MIGRATION_REVISION)

    columns = _columns(db_path)
    assert COLUMN in columns
    assert columns[COLUMN]["nullable"] is True
    assert "VARCHAR" in str(columns[COLUMN]["type"]).upper()

    indexes = _indexes(db_path)
    lineage_index = indexes[INDEX]
    assert lineage_index["column_names"] == [COLUMN]
    assert bool(lineage_index["unique"]) is False
    # The pre-existing lookup/column indexes were not dropped or recreated.
    assert indexes[FILE_LOOKUP_INDEX]["column_names"] == [
        "source", "external_id", "status"]
    assert "ix_dataset_entries_workspace_id" in indexes
    assert "ix_dataset_entries_external_id" in indexes
    assert _unique_constraints(db_path) == {
        "uq_dataset_entries_version": [
            "source_kind", "source", "external_id", "content_hash",
            "entity_name"],
    }

    # Every old row and value survived; no backfill inferred lineage.
    assert _snapshot(db_path) == before
    engine = sa.create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            assert connection.execute(sa.text(
                f"SELECT COUNT(*) FROM {TABLE} WHERE {COLUMN} IS NOT NULL"
            )).scalar_one() == 0
            assert connection.execute(sa.text(
                "SELECT version_num FROM alembic_version"
            )).scalar_one() == MIGRATION_REVISION
    finally:
        engine.dispose()

    _assert_unique_constraint_enforced(db_path)

    # The upgraded column accepts the exact lineage value the service writes.
    engine = sa.create_engine(f"sqlite:///{db_path}")
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(f"UPDATE {TABLE} SET {COLUMN} = :doc "
                        "WHERE id = :id"),
                {"doc": "doc-123", "id": "entry-active"},
            )
        with engine.connect() as connection:
            assert connection.execute(sa.text(
                f"SELECT {COLUMN} FROM {TABLE} WHERE id = 'entry-active'"
            )).scalar_one() == "doc-123"
    finally:
        engine.dispose()


def test_upgrade_is_idempotent_on_an_already_upgraded_database(tmp_path):
    db_path = tmp_path / "already-upgraded.db"
    _build_pre_migration_database(db_path)
    _run_alembic(tmp_path, db_path, "upgrade", MIGRATION_REVISION)
    before = _snapshot(db_path)

    # Calling the migration body again must not add a duplicate column/index
    # or touch the stored rows.
    _direct_upgrade(db_path, calls=2)

    assert _snapshot(db_path) == before
    columns = [name for name in _columns(db_path) if name == COLUMN]
    assert columns == [COLUMN]
    assert _indexes(db_path)[INDEX]["column_names"] == [COLUMN]
    _assert_unique_constraint_enforced(db_path)


def test_partial_upgrade_restores_a_missing_index_without_touching_rows(
        tmp_path):
    db_path = tmp_path / "missing-index.db"
    _build_pre_migration_database(db_path)
    _run_alembic(tmp_path, db_path, "upgrade", MIGRATION_REVISION)
    before = _snapshot(db_path)

    engine = sa.create_engine(f"sqlite:///{db_path}")
    try:
        with engine.begin() as connection:
            connection.execute(sa.text(f"DROP INDEX {INDEX}"))
    finally:
        engine.dispose()
    assert INDEX not in _indexes(db_path)

    _direct_upgrade(db_path, calls=1)

    assert _indexes(db_path)[INDEX]["column_names"] == [COLUMN]
    assert _snapshot(db_path) == before


def test_missing_table_is_a_safe_noop_for_the_fresh_create_all_path(
        tmp_path):
    db_path = tmp_path / "no-tables.db"
    engine = sa.create_engine(f"sqlite:///{db_path}")
    try:
        with engine.begin() as connection:
            connection.execute(sa.text(
                "CREATE TABLE unrelated (id VARCHAR PRIMARY KEY)"))
    finally:
        engine.dispose()

    _direct_upgrade(db_path, calls=2)

    engine = sa.create_engine(f"sqlite:///{db_path}")
    try:
        assert TABLE not in sa.inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_current_createall_schema_is_a_safe_noop(tmp_path):
    db_path = tmp_path / "current-schema.db"
    _build_current_schema_database(db_path)
    before = _snapshot(db_path)
    assert _columns(db_path)[COLUMN]["nullable"] is True

    _direct_upgrade(db_path, calls=2)

    assert _snapshot(db_path) == before
    assert _indexes(db_path)[INDEX]["column_names"] == [COLUMN]


def test_downgrade_drops_only_the_lineage_upgrade(tmp_path):
    db_path = tmp_path / "round-trip.db"
    _build_pre_migration_database(db_path)
    before = _snapshot(db_path)
    _run_alembic(tmp_path, db_path, "upgrade", MIGRATION_REVISION)

    _run_alembic(tmp_path, db_path, "downgrade", PRE_REVISION)

    assert COLUMN not in _columns(db_path)
    assert INDEX not in _indexes(db_path)
    assert FILE_LOOKUP_INDEX in _indexes(db_path)
    assert _snapshot(db_path) == before
    assert _unique_constraints(db_path) == {
        "uq_dataset_entries_version": [
            "source_kind", "source", "external_id", "content_hash",
            "entity_name"],
    }
    _assert_unique_constraint_enforced(db_path)

    # The same database upgrades again (re-deploy), still without backfill.
    _run_alembic(tmp_path, db_path, "upgrade", MIGRATION_REVISION)
    assert _columns(db_path)[COLUMN]["nullable"] is True
    assert _indexes(db_path)[INDEX]["column_names"] == [COLUMN]
    assert _snapshot(db_path) == before


# ---------------------------------------------------------------------------
# Static contracts (no PostgreSQL connection)
# ---------------------------------------------------------------------------
def test_orm_and_migration_agree_on_the_lineage_shape():
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    from core.models import DatasetEntry

    column = DatasetEntry.__table__.c[COLUMN]
    assert column.nullable is True
    assert isinstance(column.type, sa.String)
    assert INDEX in {index.name for index in DatasetEntry.__table__.indexes}

    migration = _load_migration()
    assert migration.TABLE == TABLE
    assert migration.COLUMN == COLUMN
    assert migration.INDEX == INDEX


def test_revision_chains_to_previous_head_within_version_column_width():
    migration = _load_migration()
    assert migration.revision == MIGRATION_REVISION
    assert migration.down_revision == PRE_REVISION
    # SQLite and existing PostgreSQL alembic_version is VARCHAR(32).
    assert len(migration.revision) <= 32
    assert len(PRE_REVISION) <= 32


def test_postgresql_ddl_is_additive_and_static_only():
    """Compile the exact PostgreSQL DDL; this never opens a PG connection.

    The migration is not executed against PostgreSQL here because the repo's
    only PostgreSQL fixture targets a shared ``localhost:5433`` e2e database,
    which is not an isolated scratch harness. A real PG upgrade remains
    unverified by this file and is not claimed.
    """
    metadata = sa.MetaData()
    table = sa.Table(
        TABLE,
        metadata,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(COLUMN, sa.String(), nullable=True),
    )
    lineage_index = sa.Index(INDEX, table.c[COLUMN])
    dialect = postgresql.dialect()

    column_ddl = str(
        CreateColumn(table.c[COLUMN]).compile(dialect=dialect))
    assert column_ddl == f"{COLUMN} VARCHAR"
    assert "NOT NULL" not in column_ddl
    assert "DEFAULT" not in column_ddl

    index_ddl = str(CreateIndex(lineage_index).compile(dialect=dialect))
    assert f"CREATE INDEX {INDEX}" in index_ddl
    assert f"ON {TABLE} ({COLUMN})" in index_ddl

    source = MIGRATION_FILE.read_text()
    assert "op.add_column(" in source
    assert "op.create_index(" in source
    assert "batch_alter_table" in source  # downgrade only
    # No data rewrite/backfill, no table rebuild, no live PG e2e URL.
    for forbidden in (
        "op.execute(",
        "UPDATE ",
        "DELETE FROM",
        "INSERT INTO",
        "op.create_table(",
        "op.drop_table(",
        "postgresql://",
        "localhost:5433",
    ):
        assert forbidden not in source
