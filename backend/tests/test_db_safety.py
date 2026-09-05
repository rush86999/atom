"""db_safety: storage-conscious snapshots + Lance version cleanup.

The box runs tight on disk (2026-09-04), so the safety net itself must not
become the storage problem: snapshots are gzipped, pruned per-label, skipped
under TESTING, and skip entirely when free space is under the floor.
"""
import gzip
import os
import sqlite3
import types

import pytest

from core import db_safety


@pytest.fixture()
def scratch_db(tmp_path, monkeypatch):
    """A tiny live-DB stand-in + isolated backup dir."""
    monkeypatch.setattr(db_safety, "_BACKUP_DIR", str(tmp_path / "backups"))
    db = tmp_path / "atom.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE users (id TEXT)")
    con.execute("INSERT INTO users VALUES ('u-1')")
    con.commit()
    con.close()
    monkeypatch.setattr(db_safety, "live_db_path", lambda: str(db))
    monkeypatch.delenv("TESTING", raising=False)
    return db


def test_snapshot_is_gzipped_and_restores_a_valid_db(scratch_db):
    dest = db_safety.snapshot_db("cycle")
    assert dest and dest.endswith(".db.gz")
    raw = dest + ".restored"
    with gzip.open(dest, "rb") as fin, open(raw, "wb") as fout:
        fout.write(fin.read())
    con = sqlite3.connect(raw)
    assert con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    con.close()
    os.remove(raw)


def test_snapshot_prunes_per_label_keep(scratch_db):
    for i in range(4):
        old = os.path.join(db_safety._BACKUP_DIR, f"atom-cycle-2026010{i}-000000.db.gz")
        os.makedirs(db_safety._BACKUP_DIR, exist_ok=True)
        with open(old, "wb") as f:
            f.write(b"stale")
    dest = db_safety.snapshot_db("cycle", keep=2)
    kept = sorted(f for f in os.listdir(db_safety._BACKUP_DIR) if f.endswith(".db.gz"))
    assert len(kept) == 2
    assert os.path.basename(dest) == kept[-1]  # newest survives


def test_snapshot_skips_under_testing(scratch_db, monkeypatch):
    monkeypatch.setenv("TESTING", "1")
    assert db_safety.snapshot_db("cycle") is None
    assert not os.path.exists(db_safety._BACKUP_DIR)


def test_snapshot_skips_when_disk_below_floor(scratch_db, monkeypatch):
    monkeypatch.setenv("ATOM_DB_SNAPSHOT_MIN_FREE_MB", "999999999")
    assert db_safety.snapshot_db("cycle") is None
    assert not os.path.exists(db_safety._BACKUP_DIR)


def test_lance_cleanup_walks_every_workspace_table(tmp_path, monkeypatch):
    monkeypatch.delenv("TESTING", raising=False)
    root = tmp_path / "atom_memory"
    for rel in ("default/documents.lance", "default/atom_communications.lance",
                "shared/t1.lance"):
        (root / rel / "_versions").mkdir(parents=True)
    calls = []

    fake_table = types.SimpleNamespace(
        cleanup_old_versions=lambda **kw: calls.append(kw))
    fake_lancedb = types.SimpleNamespace(
        connect=lambda parent: types.SimpleNamespace(
            open_table=lambda table: calls.append((parent, table)) or fake_table))

    import sys
    monkeypatch.setitem(sys.modules, "lancedb", fake_lancedb)
    summary = db_safety.lance_version_cleanup_step(retention_hours=24, root=str(root))

    assert summary["cleaned"] == 3
    assert summary["errors"] == 0
    assert {c[1] for c in calls if isinstance(c, tuple)} == {
        "documents", "atom_communications", "t1"}
    assert all("older_than" in kw for kw in calls if isinstance(kw, dict))


def test_lance_cleanup_survives_missing_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("TESTING", raising=False)
    summary = db_safety.lance_version_cleanup_step(root=str(tmp_path / "nope"))
    assert summary["cleaned"] == 0
    assert summary.get("reason") == "no_atom_memory_dir"
