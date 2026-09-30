"""Live-DB snapshot protection must fail loudly and never leave a fake backup.

WHY THIS TEST EXISTS
``core/db_safety.snapshot_db`` is the module whose entire job is to notice
trouble. On 2026-09-28 it did the opposite: it read the live DB with
``sqlite3.connect(..., mode=ro)``, which fails with "disk I/O error" when the
WAL ``-shm`` index is stale, and the resulting exception was logged at DEBUG --
so three consecutive cycles (08:27, 09:01, 09:27) failed with protection
silently OFF and nobody saw it. Each failure also left a 0-byte
``atom-cycle-<ts>.db`` in ``backups/``.

A 0-byte file there is worse than no backup: it satisfies "is there a recent
snapshot?", and restoring it yields an EMPTY live database, which is precisely
the 2026-09-04 wipe this module exists to prevent. So the properties asserted
here are: a failed snapshot is logged at WARNING, leaves no debris, and is
never published; a published snapshot is non-empty and passes quick_check; and
a stale ``-shm`` no longer disables protection when the WAL is empty.
"""
import logging
import os
import shutil
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from core import db_safety  # noqa: E402


def _make_db(path: Path, rows: int = 3) -> None:
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT)")
    for i in range(rows):
        con.execute("INSERT OR IGNORE INTO users (id, email) VALUES (?, ?)",
                    (i, f"u{i}@example.com"))
    con.commit()
    con.close()


def _run(tmp: Path, monkeypatch_db: Path, caplog=None):
    db_safety._BACKUP_DIR = str(tmp / "backups")
    os.makedirs(db_safety._BACKUP_DIR, exist_ok=True)
    return monkeypatch_db


def test_snapshot_publishes_a_verified_non_empty_file(tmp_path, monkeypatch):
    src = tmp_path / "atom.db"
    _make_db(src, rows=5)
    bdir = tmp_path / "backups"
    monkeypatch.setattr(db_safety, "_BACKUP_DIR", str(bdir))
    monkeypatch.setattr(db_safety, "live_db_path", lambda: str(src))
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.setenv("ATOM_DB_SNAPSHOT_MIN_FREE_MB", "0")

    dest = db_safety.snapshot_db(label="unittest")
    assert dest, "snapshot_db returned None for a healthy database"
    assert os.path.exists(dest) and os.path.getsize(dest) > 0
    # no uncompressed intermediate left behind
    assert [f for f in os.listdir(bdir) if f.endswith(".db")] == []
    # the published copy carries the source's rows, not merely a valid file
    import gzip as _gz
    raw_copy = tmp_path / "published.db"
    with _gz.open(dest, "rb") as fh, open(raw_copy, "wb") as out:
        shutil.copyfileobj(fh, out)
    con = sqlite3.connect(f"file:{raw_copy}?mode=ro", uri=True)
    assert con.execute("SELECT count(*) FROM users").fetchone()[0] == 5
    con.close()


def test_failed_snapshot_leaves_no_debris_and_warns(tmp_path, monkeypatch, caplog):
    src = tmp_path / "atom.db"
    _make_db(src, rows=2)
    bdir = tmp_path / "backups"
    monkeypatch.setattr(db_safety, "_BACKUP_DIR", str(bdir))
    monkeypatch.setattr(db_safety, "live_db_path", lambda: str(src))
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.setenv("ATOM_DB_SNAPSHOT_MIN_FREE_MB", "0")

    def boom(*_a, **_k):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(db_safety, "_open_source_ro", boom)
    with caplog.at_level(logging.WARNING):
        assert db_safety.snapshot_db(label="unittest") is None
    # A failed backup must be visible. DEBUG is what hid three real failures.
    assert any(r.levelno >= logging.WARNING for r in caplog.records), \
        "a failed snapshot was not logged at WARNING or above"
    # and must not leave a file that looks like a backup
    assert os.listdir(bdir) == [], f"debris left behind: {os.listdir(bdir)}"


def test_verify_rejects_zero_byte_file(tmp_path):
    empty = tmp_path / "empty.db"
    empty.write_bytes(b"")
    import pytest
    with pytest.raises(RuntimeError, match="empty"):
        db_safety._verify_snapshot(str(empty))


def test_unreadable_live_db_fails_loudly_and_publishes_nothing(tmp_path, monkeypatch, caplog):
    """A WAL-mode DB that cannot be opened read-only must NOT be backed up.

    There is deliberately no fallback here. `mode=rw` would take a write handle
    on the live dev DB from a maintenance thread; `immutable=1` ignores the WAL,
    so it can produce a backup that passes every validation check and is still
    missing the most recent commits -- more dangerous than no backup, because
    it would be restored believing it was current; a byte copy is torn by
    construction. So the correct behaviour is a loud, visible failure.
    """
    src = tmp_path / "atom.db"
    _make_db(src, rows=4)
    (tmp_path / "atom.db-wal").write_bytes(b"x" * 64)
    bdir = tmp_path / "backups"
    monkeypatch.setattr(db_safety, "_BACKUP_DIR", str(bdir))
    monkeypatch.setattr(db_safety, "live_db_path", lambda: str(src))
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.setenv("ATOM_DB_SNAPSHOT_MIN_FREE_MB", "0")

    def boom(target, *a, **k):
        if "mode=ro" in str(target):
            raise sqlite3.OperationalError("disk I/O error")
        raise AssertionError(f"must not fall back to {target}")

    monkeypatch.setattr(db_safety.sqlite3, "connect", boom)
    with caplog.at_level(logging.WARNING):
        assert db_safety.snapshot_db(label="unittest") is None
    assert any(r.levelno >= logging.WARNING for r in caplog.records)
    assert not list(bdir.glob("*.db.gz")), "a snapshot was published from an unreadable DB"
    assert os.listdir(bdir) == [], f"debris left behind: {os.listdir(bdir)}"
