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


def _uri(path: Path, mode: str = "rw") -> str:
    return f"sqlite:///file:{quote(str(path), safe='/')}?mode={mode}&uri=true"


def _seed_direct(path: Path):
    con = sqlite3.connect(path)
    try:
        for table in TABLES:
            con.execute(f"CREATE TABLE {table}(id TEXT)")
            con.execute(f"INSERT INTO {table} VALUES ('{table}-row')")
        con.commit()
    finally:
        con.close()


def _seed_engine(path: Path):
    uri = _uri(path, mode="rwc")
    engine = create_engine(uri)
    try:
        with engine.begin() as conn:
            for table in TABLES:
                conn.execute(text(f"CREATE TABLE {table}(id TEXT)"))
                conn.execute(text(f"INSERT INTO {table} VALUES ('{table}-row')"))
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
    _seed_engine(source)
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
    _seed_direct(source)
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
    _seed_direct(source)
    _set_database_url(monkeypatch, _uri(source))

    dest = db_safety.snapshot_db("unittest")
    assert dest and os.path.isfile(dest)
    assert _read_snapshot(dest, tmp_path)["counts"] == {
        table: 1 for table in TABLES}


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
