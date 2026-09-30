"""db_safety: the failures that silently disabled the 2026-09-04 wipe net.

Incident 2026-09-28: ``write_fingerprint`` opened the fingerprint with
``open(path, "w")`` -- which truncates BEFORE the dump -- and then died on
``NameError: name 'json' is not defined`` (``json`` was never imported),
with the failure swallowed at DEBUG. Every maintenance cycle therefore left a
0-byte fingerprint. ``check_wipe_at_startup`` only re-seeds when the file is
*absent*, so the 0-byte file was never healed and never re-seeded: wipe
detection was simply off, for the whole day, silently.

Every test here runs against a scratch database in a tmp dir. ``snapshot_db``
returns early under ``TESTING=1``, so the snapshot tests unset it for the
duration -- the risk they carry is pointing ``live_db_path`` at the live dev
DB, which the fixture replaces with a tmp file.
"""
import gzip
import json
import logging
import os
import sqlite3

import pytest

from core import db_safety


def _make_scratch_db(path, users=3, agents=9, canvases=2):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE users (id TEXT)")
    con.execute("CREATE TABLE agent_registry (id TEXT)")
    con.execute("CREATE TABLE canvases (id TEXT)")
    con.executemany("INSERT INTO users VALUES (?)", [(f"u{i}",) for i in range(users)])
    con.executemany("INSERT INTO agent_registry VALUES (?)",
                    [(f"a{i}",) for i in range(agents)])
    con.executemany("INSERT INTO canvases VALUES (?)",
                    [(f"c{i}",) for i in range(canvases)])
    con.commit()
    con.close()


@pytest.fixture()
def scratch(tmp_path, monkeypatch):
    """A tiny live-DB stand-in with isolated backup + fingerprint paths."""
    db = tmp_path / "atom.db"
    _make_scratch_db(db)
    monkeypatch.setattr(db_safety, "_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setattr(db_safety, "_FINGERPRINT_PATH",
                        str(tmp_path / "db_fingerprint.json"))
    monkeypatch.setattr(db_safety, "live_db_path", lambda: str(db))
    # snapshot_db is a hard no-op under TESTING=1; the tests that exercise it
    # need it off, and it is off here for every test in this module.
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.delenv("ATOM_DB_SNAPSHOT_MIN_FREE_MB", raising=False)
    return db


# --------------------------------------------------------------------------
# 1. An interrupted fingerprint write must not destroy the last good one.
# --------------------------------------------------------------------------

def test_interrupted_fingerprint_write_keeps_previous_baseline(scratch, monkeypatch):
    """The truncate-then-dump bug, as a regression test.

    Under the old code this sequence left a 0-byte file: ``open(path, "w")``
    truncates, then the dump raises. Now the write goes to a temp file, so the
    previous baseline survives intact and readable.
    """
    first = db_safety.write_fingerprint()
    assert first is not None
    before = open(db_safety._FINGERPRINT_PATH).read()
    assert json.loads(before)["counts"]["agent_registry"] == 9

    real_dump = json.dump

    def dump_then_explode(obj, fp, **kwargs):
        fp.write('{"counts": {"users": 3, "agent_reg')  # partial write...
        fp.flush()
        raise RuntimeError("simulated interrupt mid-dump")

    monkeypatch.setattr(db_safety.json, "dump", dump_then_explode)
    assert db_safety.write_fingerprint() is None
    monkeypatch.setattr(db_safety.json, "dump", real_dump)

    # The previous valid baseline is still there, byte for byte, and parses.
    after = open(db_safety._FINGERPRINT_PATH).read()
    assert after == before
    assert json.loads(after)["counts"]["agent_registry"] == 9
    # ...and the failed write left no temp debris beside it.
    leftovers = [f for f in os.listdir(os.path.dirname(db_safety._FINGERPRINT_PATH))
                 if f.startswith(".fingerprint-")]
    assert leftovers == []


def test_fingerprint_write_failure_is_logged_loudly(scratch, monkeypatch, caplog):
    """A fingerprint that cannot be written is a protection failure, not a debug line."""
    def boom(*a, **k):
        raise RuntimeError("no space left on device")

    monkeypatch.setattr(db_safety, "_quick_counts", boom)
    with caplog.at_level(logging.ERROR, logger="core.db_safety"):
        assert db_safety.write_fingerprint() is None
    assert any(r.levelno >= logging.ERROR
               and "fingerprint write FAILED" in r.getMessage()
               for r in caplog.records), [r.getMessage() for r in caplog.records]


# --------------------------------------------------------------------------
# 2. An empty/corrupt fingerprint at startup is a VISIBLE protection failure
#    and must never be re-seeded from current counts.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("corrupt", [
    pytest.param("", id="zero_bytes"),
    pytest.param("{ this is not json", id="not_json"),
    pytest.param('{"taken_at": "2026-09-28T00:00:00+00:00"}', id="no_counts"),
])
def test_broken_fingerprint_is_loud_and_never_reseeded(scratch, corrupt, caplog):
    """Reseeding from current counts is what would let a wipe hide itself.

    If the baseline is replaced with today's numbers, a wiped DB becomes the
    new normal and no comparison is ever possible again. So the file must be
    left exactly as found, and the failure must be CRITICAL.
    """
    os.makedirs(os.path.dirname(db_safety._FINGERPRINT_PATH), exist_ok=True)
    with open(db_safety._FINGERPRINT_PATH, "w") as f:
        f.write(corrupt)

    with caplog.at_level(logging.DEBUG, logger="core.db_safety"):
        db_safety.check_wipe_at_startup()

    criticals = [r for r in caplog.records if r.levelno >= logging.CRITICAL]
    assert criticals, "a broken fingerprint must be CRITICAL, not silent"
    msg = criticals[0].getMessage()
    assert "WIPE DETECTION IS OFF" in msg
    assert "UNMONITORED" in msg
    # The file is untouched: still corrupt, still 0 bytes, NOT reseeded.
    assert open(db_safety._FINGERPRINT_PATH).read() == corrupt
    assert os.path.getsize(db_safety._FINGERPRINT_PATH) == len(corrupt)


def test_genuine_agent_collapse_still_logs_the_critical_restore_hint(scratch, caplog):
    """The behaviour the wipe net exists for must survive all of the above."""
    baseline = db_safety.write_fingerprint()
    assert baseline["counts"]["agent_registry"] == 9

    con = sqlite3.connect(scratch)
    con.execute("DELETE FROM agent_registry")
    con.commit()
    con.close()

    with caplog.at_level(logging.DEBUG, logger="core.db_safety"):
        db_safety.check_wipe_at_startup()

    criticals = [r.getMessage() for r in caplog.records if r.levelno >= logging.CRITICAL]
    assert any("DB WIPE SUSPECTED" in m for m in criticals), criticals
    assert any("restore" in m.lower() for m in criticals), criticals


def test_absent_fingerprint_is_still_a_first_run(scratch):
    """No file at all is a genuine first run and may initialize itself."""
    assert db_safety.write_fingerprint() is not None
    db_safety.check_wipe_at_startup()
    fp, problem = db_safety.load_fingerprint()
    assert problem is None
    assert fp["counts"]["agent_registry"] == 9


# --------------------------------------------------------------------------
# 3. A backup that fails validation publishes nothing and prunes nothing.
# --------------------------------------------------------------------------

def test_failed_validation_publishes_nothing_and_prunes_nothing(scratch, monkeypatch):
    backups = db_safety._BACKUP_DIR
    os.makedirs(backups, exist_ok=True)
    # Two pre-existing good snapshots that must survive a failed attempt.
    good = []
    for i in range(2):
        p = os.path.join(backups, f"atom-cycle-2026010{i}-000000.db.gz")
        with open(p, "wb") as f:
            f.write(b"pre-existing good snapshot")
        good.append(p)

    monkeypatch.setattr(db_safety, "_verify_snapshot",
                        lambda *a, **k: (_ for _ in ()).throw(
                            RuntimeError("validation failed")))

    assert db_safety.snapshot_db("cycle", keep=1) is None

    # Nothing new was published under a final name...
    published = sorted(f for f in os.listdir(backups) if f.endswith(".db.gz"))
    assert published == sorted(os.path.basename(p) for p in good)
    # ...nothing partial or empty was left behind, sidecars included...
    assert [f for f in os.listdir(backups) if f.startswith(".")] == []
    # ...and the pre-existing backups were NOT pruned, even though keep=1.
    for p in good:
        assert os.path.exists(p) and os.path.getsize(p) > 0


def test_snapshot_that_would_be_short_of_the_source_is_refused(scratch, monkeypatch):
    """A copy that passes integrity_check but lost rows is still not a backup."""
    dest = db_safety.snapshot_db("cycle")
    assert dest, "the control case must succeed"

    real_verify = db_safety._verify_snapshot

    def overstate(path, expect_counts=None):
        # pretend the source had far more rows than it did
        return real_verify(path, {**(expect_counts or {}), "agent_registry": 9999})

    monkeypatch.setattr(db_safety, "_verify_snapshot", overstate)
    before = set(os.listdir(db_safety._BACKUP_DIR))
    assert db_safety.snapshot_db("cycle") is None
    assert set(os.listdir(db_safety._BACKUP_DIR)) == before


def test_successful_snapshot_leaves_no_partial_or_sidecar_debris(scratch):
    """sqlite grows -wal/-shm beside a backup target; they must be cleaned up.

    Five orphan ``*.db-wal``/``*.db-shm`` pairs from September are still
    sitting in backups/, which is what this closes.
    """
    dest = db_safety.snapshot_db("cycle")
    assert dest and os.path.getsize(dest) > 0
    files = os.listdir(db_safety._BACKUP_DIR)
    assert files == [os.path.basename(dest)], files
    assert not [f for f in files if f.endswith(("-wal", "-shm", ".partial"))]
    # and the published artifact really restores a usable database
    raw = dest + ".check"
    with gzip.open(dest, "rb") as fin, open(raw, "wb") as fout:
        fout.write(fin.read())
    con = sqlite3.connect(raw)
    assert con.execute("SELECT COUNT(*) FROM agent_registry").fetchone()[0] == 9
    con.close()
    os.remove(raw)


# --------------------------------------------------------------------------
# 4. A snapshot failure is distinguishable from a success in the return value.
# --------------------------------------------------------------------------

def test_maintenance_step_reports_failure_distinctly(scratch, monkeypatch):
    monkeypatch.setattr(db_safety, "snapshot_db", lambda *a, **k: None)
    monkeypatch.setattr(db_safety, "write_fingerprint", lambda: None)
    out = db_safety.maintenance_db_safety_step()
    assert out["snapshot"] is None
    assert out["fingerprint"] is False
    assert out["protected"] is False
    assert out["snapshot_error"] and out["fingerprint_error"]


def test_maintenance_step_reports_success_distinctly(scratch):
    out = db_safety.maintenance_db_safety_step()
    assert out["snapshot"] and os.path.exists(out["snapshot"])
    assert out["fingerprint"] is True
    assert out["protected"] is True
    assert "snapshot_error" not in out and "fingerprint_error" not in out


def test_snapshot_ok_but_fingerprint_failed_is_not_reported_as_protected(
        scratch, monkeypatch):
    """Both halves matter: a stale fingerprint is how 2026-09-28 happened."""
    monkeypatch.setattr(db_safety, "write_fingerprint", lambda: None)
    out = db_safety.maintenance_db_safety_step()
    assert out["snapshot"]  # a real backup was published
    assert out["fingerprint"] is False
    assert out["protected"] is False


# --------------------------------------------------------------------------
# 5. Free space below the floor skips cleanly, and says so.
# --------------------------------------------------------------------------

def test_free_space_below_floor_skips_cleanly_and_says_so(scratch, monkeypatch, caplog):
    monkeypatch.setenv("ATOM_DB_SNAPSHOT_MIN_FREE_MB", "999999999")
    with caplog.at_level(logging.DEBUG, logger="core.db_safety"):
        assert db_safety.snapshot_db("cycle") is None
    warns = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("SKIPPED" in m and "free" in m for m in warns), warns
    assert not os.path.exists(db_safety._BACKUP_DIR)


def test_snapshot_never_falls_back_to_a_weaker_read_mode(scratch, monkeypatch):
    """If the source cannot be opened read-only, we fail -- we do not improvise.

    A weaker read (immutable=1, or a byte copy) can produce a backup that
    validates but is missing unmerged WAL commits.
    """
    opened = []

    def refuse(database, **kwargs):
        opened.append(database)
        raise sqlite3.OperationalError(
            "disk I/O error", "unable to open database file")

    monkeypatch.setattr(sqlite3, "connect", refuse)
    assert db_safety.snapshot_db("cycle") is None
    assert opened, "the source must have been attempted"
    assert all("mode=ro" in u for u in opened), opened
    # The backup dir may exist (makedirs runs first), but it holds nothing.
    assert os.listdir(db_safety._BACKUP_DIR) == []
