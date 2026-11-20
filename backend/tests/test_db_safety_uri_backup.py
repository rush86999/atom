"""SQLite URI backup consumer: exact target + safe read-only URI encoding.

Two root-verified negatives on the shared DB safety net:

* ``core.db_safety.live_db_path`` split ``sqlite:///`` textually, so a valid
  main-DB ``file:...?...uri=true`` target looked like a non-filesystem path
  and ``snapshot_db`` silently skipped the backup;
* ``_open_source_ro`` interpolated a filesystem path into ``file:{path}?mode=ro``
  unescaped. A filename containing ``#`` (or ``?``/``%``) changed the URI
  parse, dropped ``mode=ro``, opened/created a different sibling writable
  file, and still reported read-only.

Controls use only synthetic scratch databases and monkeypatched backup /
fingerprint directories. ``TESTING=0`` is set only for the snapshot call with
an explicit own scratch DATABASE_URL; no live backend/dev.db or
data/atom.db is imported or opened. The ordinary SQLite path and existing WAL
/ integrity / no-prune-on-failure behavior are preserved.
"""
from __future__ import annotations

import gzip
import json
import os
import sqlite3
from pathlib import Path
from urllib.parse import quote

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from core import db_safety

TABLES = ("users", "agent_registry", "canvases")


@pytest.fixture()
def safety_roots(tmp_path, monkeypatch):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    monkeypatch.setattr(db_safety, "_BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr(db_safety, "_FINGERPRINT_PATH",
                        str(tmp_path / "fingerprint.json"))
    # Snapshot is a hard no-op under TESTING=1; these tests own scratch DBs
    # and monkeypatched publish directories, so the explicit dev path is safe.
    monkeypatch.setenv("TESTING", "0")
    return tmp_path, backup_dir


# SQLAlchemy 2.0 preserves outer database percent escapes, while 2.1
# consumes one outer layer; SQLite itself decodes once in both. Probe
# make_url directly (never the resolver under test) so the fixtures get the
# right number of encoding layers without a hardcoded version check.
_PROBE_URL = "sqlite:///file:probe%2520name?mode=rw&uri=true"
_OUTER_DECODES_ESCAPES = (
    "%2520" not in (make_url(_PROBE_URL).database or "")
)


def _sqlite_uri(path: Path, mode: str = "rw", suffix: str = "") -> str:
    """Build the inner SQLite ``file:`` URI with any real delimiter intact."""
    base = f"file:{quote(str(path), safe='/')}"
    if suffix.startswith("#"):
        return f"{base}{suffix}?mode={mode}&uri=true"
    if suffix.startswith("?"):
        return f"{base}{suffix}&mode={mode}&uri=true"
    return f"{base}?mode={mode}&uri=true"


def _outer_url(sqlite_uri: str) -> str:
    """Adapt a SQLite URI to an SQLAlchemy URL for the active version."""
    if _OUTER_DECODES_ESCAPES:
        # make_url() removes one outer layer. Preserve real URI delimiters,
        # but encode '#' so it cannot discard the outer query as a fragment.
        sqlite_uri = quote(sqlite_uri, safe="/:?&=")
    return f"sqlite:///{sqlite_uri}"


def _uri(path: Path, mode: str = "rw") -> str:
    return _outer_url(_sqlite_uri(path, mode))


def _seed_direct(path: Path):
    con = sqlite3.connect(path)
    try:
        for table in TABLES:
            con.execute(f"CREATE TABLE {table}(id TEXT)")
            con.execute(f"INSERT INTO {table} VALUES ('{table}-row')")
        con.commit()
    finally:
        con.close()


def _seed_engine(path: Path) -> str:
    """Create/seed through the real SQLAlchemy engine; return its actual file."""
    uri = _uri(path, mode="rwc")
    engine = create_engine(uri)
    try:
        with engine.begin() as conn:
            for table in TABLES:
                conn.execute(text(f"CREATE TABLE {table}(id TEXT)"))
                conn.execute(text(f"INSERT INTO {table} VALUES ('{table}-row')"))
            opened = conn.execute(text("PRAGMA database_list")).fetchone()[2]
        return opened
    finally:
        engine.dispose()


def _read_snapshot(dest: str, tmp_path: Path) -> dict:
    raw = tmp_path / "snapshot.raw"
    with gzip.open(dest, "rb") as src:
        raw.write_bytes(src.read())
    con = sqlite3.connect(raw)
    try:
        counts = {
            table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in TABLES
        }
        marker = con.execute("SELECT id FROM users").fetchone()[0]
    finally:
        con.close()
    return {"counts": counts, "marker": marker}


def _set_database_url(monkeypatch, uri: str):
    import core.database

    monkeypatch.setattr(core.database, "DATABASE_URL", uri)


def test_valid_main_db_uri_resolves_and_snapshots(safety_roots, monkeypatch):
    tmp_path, _ = safety_roots
    source = tmp_path / "synthetic world.sqlite"
    assert _seed_engine(source) == str(source)
    uri = _uri(source)
    _set_database_url(monkeypatch, uri)

    assert db_safety.live_db_path() == str(source)
    con, mode = db_safety._open_source_ro(str(source))
    try:
        assert mode == "mode=ro"
        assert con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    finally:
        con.close()

    dest = db_safety.snapshot_db("unittest")
    assert dest and os.path.isfile(dest)
    parsed = _read_snapshot(dest, tmp_path)
    assert parsed["counts"] == {table: 1 for table in TABLES}
    assert parsed["marker"] == "users-row"


def test_fingerprint_uses_uri_target(safety_roots, monkeypatch):
    tmp_path, _ = safety_roots
    source = tmp_path / "fingerprint world.sqlite"
    _seed_direct(source)
    _set_database_url(monkeypatch, _uri(source))

    fp = db_safety.write_fingerprint()
    assert fp is not None
    assert fp["counts"] == {table: 1 for table in TABLES}
    stored = json.loads(Path(db_safety._FINGERPRINT_PATH).read_text())
    assert stored["counts"] == {table: 1 for table in TABLES}


@pytest.mark.parametrize("filename", [
    "world #1.sqlite",
    "world ?1.sqlite",
    "world %1.sqlite",
])
def test_special_filename_opens_exact_file_read_only_and_snapshots(
    safety_roots, monkeypatch, filename,
):
    tmp_path, _ = safety_roots
    source = tmp_path / filename
    # The real engine establishes the exact special-character filename.
    assert _seed_engine(source) == str(source)
    _set_database_url(monkeypatch, _uri(source))

    assert db_safety.live_db_path() == str(source)

    con, mode = db_safety._open_source_ro(str(source))
    try:
        opened = con.execute("PRAGMA database_list").fetchone()[2]
        assert opened == str(source)
        assert mode == "mode=ro"
        with pytest.raises(sqlite3.OperationalError):
            con.execute("CREATE TABLE must_not_write(x)")
    finally:
        con.close()

    # No truncated/unexpected sibling (e.g. "world " from a dropped fragment).
    unexpected = [
        p.name for p in tmp_path.iterdir()
        if p != source and not p.name.startswith("backups")
        and not p.name.startswith("snapshot") and not p.name.startswith("fingerprint")
    ]
    assert unexpected == []

    dest = db_safety.snapshot_db("unittest")
    assert dest and os.path.isfile(dest)
    parsed = _read_snapshot(dest, tmp_path)
    assert parsed["counts"] == {table: 1 for table in TABLES}
    assert parsed["marker"] == "users-row"


def test_snapshot_publish_directory_with_special_chars(
    safety_roots, monkeypatch,
):
    tmp_path, _ = safety_roots
    backup_dir = tmp_path / "backups #1"
    backup_dir.mkdir()
    monkeypatch.setattr(db_safety, "_BACKUP_DIR", str(backup_dir))
    source = tmp_path / "world #1.sqlite"
    assert _seed_engine(source) == str(source)
    _set_database_url(monkeypatch, _uri(source))

    dest = db_safety.snapshot_db("unittest")
    assert dest and os.path.isfile(dest)
    assert _read_snapshot(dest, tmp_path)["counts"] == {
        table: 1 for table in TABLES}


@pytest.mark.parametrize("suffix", ["#ignored", "?cache=private"])
def test_encoded_fragment_or_query_suffix_targets_actual_protected_file(
    safety_roots, monkeypatch, suffix,
):
    """A real URI delimiter must not hide or retarget the protected file."""
    tmp_path, _ = safety_roots
    backend = tmp_path / "synthetic-backend"
    target = backend / "data" / "atom.db"
    target.parent.mkdir(parents=True)
    _seed_direct(target)
    # Build the SQLite layer with an actual delimiter, then adapt only the
    # outer SQLAlchemy URL so make_url hands that same URI to SQLite.
    uri = _outer_url(_sqlite_uri(target, suffix=suffix))
    _set_database_url(monkeypatch, uri)

    engine_opened = None
    marker = None
    engine = create_engine(uri)
    try:
        with engine.connect() as conn:
            engine_opened = conn.execute(
                text("PRAGMA database_list")).fetchone()[2]
            marker = conn.execute(text("SELECT id FROM users")).fetchone()[0]
    except SQLAlchemyError:
        # A true '#' fragment is optional in SQLite URI handling. When the
        # runtime rejects it, keep the independent guarded-path checks below.
        if suffix != "#ignored":
            raise
        engine_opened = None
    finally:
        engine.dispose()

    if engine_opened is not None:
        assert engine_opened == str(target)
        assert marker == "users-row"

    from core.local_paths import resolve_sqlite_file_path

    assert resolve_sqlite_file_path(uri) == str(target)
    assert db_safety.live_db_path() == str(target)

    # Independently of SQLAlchemy's URL parsing, the production opener must
    # hit the exact protected file and refuse writes.
    con, mode = db_safety._open_source_ro(str(target))
    try:
        opened = con.execute("PRAGMA database_list").fetchone()[2]
        assert opened == str(target)
        assert mode == "mode=ro"
        with pytest.raises(sqlite3.OperationalError):
            con.execute("CREATE TABLE must_not_write(x)")
    finally:
        con.close()

    # No literal delimiter-bearing sibling was created by the URI.
    assert sorted(p.name for p in target.parent.iterdir()) == [target.name]

    dest = db_safety.snapshot_db("unittest")
    assert dest and os.path.isfile(dest)
    parsed = _read_snapshot(dest, tmp_path)
    assert parsed["counts"] == {table: 1 for table in TABLES}
    assert parsed["marker"] == "users-row"


def test_plain_nonuri_mode_memory_query_is_still_a_disk_file(
    safety_roots, monkeypatch,
):
    tmp_path, _ = safety_roots
    source = tmp_path / "plain-memory-query.sqlite"
    _seed_direct(source)
    uri = f"sqlite:///{source}?mode=memory"
    # The actual engine ignores the query without uri=true and opens the file.
    engine = create_engine(uri)
    try:
        with engine.connect() as conn:
            opened = conn.execute(text("PRAGMA database_list")).fetchone()[2]
    finally:
        engine.dispose()
    assert opened == str(source)
    _set_database_url(monkeypatch, uri)

    from core.local_paths import resolve_sqlite_file_path

    assert resolve_sqlite_file_path(uri) == str(source)
    assert db_safety.live_db_path() == str(source)
    dest = db_safety.snapshot_db("unittest")
    assert dest and os.path.isfile(dest)
    assert _read_snapshot(dest, tmp_path)["marker"] == "users-row"


def test_relative_uri_resolves_actual_cwd(safety_roots, monkeypatch):
    tmp_path, _ = safety_roots
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "relative-world.sqlite"
    uri = "sqlite:///file:relative-world.sqlite?mode=rwc&uri=true"
    engine = create_engine(uri)
    try:
        with engine.begin() as conn:
            for table in TABLES:
                conn.execute(text(f"CREATE TABLE {table}(id TEXT)"))
                conn.execute(text(f"INSERT INTO {table} VALUES ('{table}-row')"))
            opened = conn.execute(text("PRAGMA database_list")).fetchone()[2]
    finally:
        engine.dispose()
    assert opened == str(source)
    _set_database_url(monkeypatch, uri)

    from core.local_paths import resolve_sqlite_file_path

    assert resolve_sqlite_file_path(uri) == str(source)
    assert db_safety.live_db_path() == str(source)


def test_ordinary_sqlite_path_is_unchanged(safety_roots, monkeypatch):
    tmp_path, _ = safety_roots
    source = tmp_path / "ordinary.sqlite"
    _seed_direct(source)
    _set_database_url(monkeypatch, f"sqlite:///{source}")

    assert db_safety.live_db_path() == str(source)
    dest = db_safety.snapshot_db("unittest")
    assert dest and os.path.isfile(dest)
    assert _read_snapshot(dest, tmp_path)["counts"] == {
        table: 1 for table in TABLES}


@pytest.mark.parametrize("uri", [
    "sqlite:///:memory:",
    "sqlite:///file:memdb1?mode=memory&cache=shared&uri=true",
    "sqlite:///file::memory:?cache=shared&uri=true",
    "postgresql://localhost/atom",
    "redis://localhost:6379/1",
    "sqlite://",
])
def test_memory_and_non_sqlite_have_no_backup_target(
    safety_roots, monkeypatch, uri,
):
    _set_database_url(monkeypatch, uri)
    assert db_safety.live_db_path() is None
    assert db_safety.snapshot_db("unittest") is None


def test_malformed_sqlite_url_skips_backup_without_guessing(
    safety_roots, monkeypatch,
):
    _set_database_url(monkeypatch, "sqlite://[")
    assert db_safety.live_db_path() is None
    assert db_safety.snapshot_db("unittest") is None
