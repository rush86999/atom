"""DB safety net for the SQLite dev database (incident 2026-09-04).

A stray script (an ephemeral "govcheck" harness from another agent session)
emptied ``backend/data/atom.db`` and the app happily re-seeded a blank world
on next start — the only recovery copies were ad-hoc. This module closes
that gap with three small, fault-isolated mechanisms:

1. ``snapshot_db``       — WAL-safe sqlite backup into ``backend/data/backups/``
   (called every maintenance cycle and by ``scripts/restart_backend.sh``
   before every restart; old snapshots pruned).
2. ``write_fingerprint`` — a tiny row-count fingerprint (users / agents /
   canvases) the maintenance cycle refreshes.
3. ``check_wipe_at_startup`` — app startup compares reality against that
   fingerprint and logs a CRITICAL (with restore hints) when the world
   shrank. Never blocks startup; a missing/first-run fingerprint just
   initializes it.

Rules for agents/humans (AGENTS.md): ad-hoc scripts NEVER connect to the
live dev DB — set ``TESTING=1`` or point ``DATABASE_URL`` at a scratch file.
"""
from __future__ import annotations

import gzip
import json
import logging
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_BACKUP_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "backups"
)
_FINGERPRINT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "db_fingerprint.json",
)
# Retention + floor are env-tunable: this dev box runs tight on disk
# (2026-09-04) and snapshots must never be the thing that fills it.
def _keep_for(label: str) -> int:
    env = "ATOM_DB_SNAPSHOT_KEEP_RESTART" if label == "restart" else "ATOM_DB_SNAPSHOT_KEEP_CYCLE"
    try:
        return max(1, int(os.getenv(env, "5")))
    except ValueError:
        return 5


def _min_free_bytes() -> float:
    try:
        return float(os.getenv("ATOM_DB_SNAPSHOT_MIN_FREE_MB", "500")) * 1024 * 1024
    except ValueError:
        return 500 * 1024 * 1024


# Below this many agents the "world shrank" comparison is meaningless
# (fresh installs and the post-wipe re-seed hold 1-4 rows).
_FINGERPRINT_MIN_AGENTS = 5

_COUNT_TABLES = ("users", "agent_registry", "canvases")


def live_db_path() -> Optional[str]:
    """The dev sqlite file this install resolves to (None for non-sqlite)."""
    try:
        from core.database import DATABASE_URL

        if not DATABASE_URL or "sqlite" not in DATABASE_URL:
            return None
        path = DATABASE_URL.split("sqlite:///", 1)[-1]
        if not path or path == ":memory:":
            return None
        return path
    except Exception:
        return None


def _quick_counts(db_path: str, con: Optional[sqlite3.Connection] = None) -> Dict[str, int]:
    """Best-effort row counts (missing tables count 0 — a wiped DB may not
    even have them yet).

    Pass an already-open ``con`` to read through it: a second read-only open
    is a second chance to fail, and the counts must come from the same
    validated connection the backup is taken through.
    """
    counts: Dict[str, int] = {}
    own = con is None
    if own:
        con, _mode = _open_source_ro(db_path)
    try:
        for table in _COUNT_TABLES:
            try:
                counts[table] = con.execute(
                    f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.OperationalError:
                counts[table] = 0
    finally:
        if own:
            con.close()
    return counts


def _open_source_ro(db_path: str) -> Tuple[sqlite3.Connection, str]:
    """Open the live DB read-only, and fail LOUDLY when that is not possible.

    ``mode=ro`` is the only mode used here, on purpose. A WAL-mode database
    that cannot be opened read-only is a database we cannot honestly back up:
    the alternatives are all worse than a visible failure.

      * ``mode=rw`` would open a write handle on the live dev DB from a
        maintenance thread -- exactly the class of stray-handle accident the
        2026-09-04 wipe came from.
      * ``immutable=1`` IGNORES the WAL. It is not a stricter read, it is a
        *lesser* one: on a live box the WAL holds committed transactions that
        are not yet in the main file, so an immutable backup can be perfectly
        valid (integrity_check ok, row counts self-consistent) while silently
        missing the most recent commits. A backup that passes validation and
        is quietly behind is more dangerous than no backup, because it will be
        restored believing it is current.
      * a byte copy of a live WAL database is torn by construction.

    So: one mode, and a full extended error if it does not work. The failure
    is recorded because on 2026-09-28 this path failed three cycles running
    (08:27, 09:01, 09:27) and every one of them was swallowed at DEBUG, which
    left three 0-byte files in backups/ that each looked like a snapshot.
    """
    uri = f"file:{db_path}?mode=ro"
    try:
        return sqlite3.connect(uri, uri=True), "mode=ro"
    except sqlite3.Error as e:
        wal_len = 0
        try:
            wal_len = os.path.getsize(db_path + "-wal")
        except OSError:
            pass
        logger.error(
            "CANNOT open the live DB read-only (%s) -- backup protection is "
            "OFF for this cycle and no snapshot will be published. "
            "sqlite_errorcode=%s sqlite_errorname=%s type=%s message=%s "
            "(WAL is %s bytes; NOT falling back to mode=rw, immutable=1 or a "
            "file copy, because each of those can produce a backup that is "
            "silently incomplete)",
            uri, getattr(e, "sqlite_errorcode", None),
            getattr(e, "sqlite_errorname", None), type(e).__name__, e, wal_len,
        )
        raise


def _remove_db_files(path: str) -> None:
    """Remove a sqlite file AND its -wal/-shm sidecars.

    Snapshot targets are opened by sqlite, so they grow sidecars; removing
    only the main file leaves ``.db-wal`` / ``.db-shm`` orphans behind in
    backups/ (five such pairs are still there from September). Worse, a
    leftover 0-byte ``-wal`` next to a real ``.db`` makes the pair look like
    a live database mid-transaction.
    """
    for candidate in (path, path + "-wal", path + "-shm", path + "-journal"):
        try:
            os.remove(candidate)
        except FileNotFoundError:
            pass
        except OSError as e:
            logger.warning("could not remove %s: %s", candidate, e)


def _verify_snapshot(path: str, expect_counts: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """Refuse to publish a snapshot that is empty, invalid, or short of the source.

    A 0-byte file in backups/ is worse than no backup at all: it satisfies a
    "do we have a recent snapshot?" check and a restore from it produces an
    EMPTY live database, which is the exact 2026-09-04 incident this module
    exists to prevent.

    ``expect_counts`` is the row-count floor read from the live source. A copy
    that validates but is missing tables is a silently incomplete backup, so
    the comparison is part of validation, not a post-hoc check.
    """
    size = os.path.getsize(path)
    if size <= 0:
        raise RuntimeError(f"snapshot is empty ({size} bytes): {path}")
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        row = con.execute("PRAGMA integrity_check").fetchone()
        if not row or row[0] != "ok":
            raise RuntimeError(f"snapshot failed integrity_check: {row!r}")
        got: Dict[str, int] = {}
        for table in _COUNT_TABLES:
            try:
                got[table] = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.OperationalError:
                got[table] = 0
    finally:
        con.close()
    if expect_counts:
        short = {t: (got.get(t), n) for t, n in expect_counts.items()
                 if got.get(t, 0) < n}
        if short:
            raise RuntimeError(
                f"snapshot lost rows relative to the live source (copy, source): {short}")
    return {"integrity_check": "ok", "size_bytes": size, "counts": got}


def snapshot_db(label: str = "cycle", keep: Optional[int] = None) -> Optional[str]:
    """WAL-safe backup of the live sqlite DB into backend/data/backups/,
    gzipped (sqlite text compresses ~4x; the box is disk-constrained).

    Nothing is published until it is proven good. The sqlite backup target is
    a hidden ``.partial`` file; it is only ``os.replace``d to a real name
    after ``integrity_check`` passes and its row counts are at least the live
    source's. On any failure the partials are removed and the previous good
    backups are left exactly as they were -- pruning runs only on success, so
    a failed attempt can never evict a working backup.

    Skips — returning None, never raising — when running under TESTING=1
    (unit tests must not snapshot the live dev DB: pytest imports got the
    snapshot running against the real file) or when free disk space is
    below ``ATOM_DB_SNAPSHOT_MIN_FREE_MB`` (a backup that fills the disk
    kills the very DB it is protecting).
    """
    if os.getenv("TESTING") == "1":
        return None
    db_path = live_db_path()
    if not db_path or not os.path.exists(db_path):
        return None
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(_BACKUP_DIR, f"atom-{label}-{ts}.db.gz")
    raw = dest[:-3]  # strip .gz for the sqlite backup target
    partial = os.path.join(_BACKUP_DIR, f".{label}-{ts}.db.partial")
    gz_partial = dest + ".partial"
    try:
        free = shutil.disk_usage(db_path).free
        if free < _min_free_bytes():
            logger.warning(
                "db snapshot (%s) SKIPPED: only %.0f MB free (floor %s MB) — "
                "free disk space or lower ATOM_DB_SNAPSHOT_MIN_FREE_MB. No "
                "snapshot was published this cycle.",
                label, free / 1024 / 1024,
                os.getenv("ATOM_DB_SNAPSHOT_MIN_FREE_MB", "500"),
            )
            return None

        os.makedirs(_BACKUP_DIR, exist_ok=True)
        src, _mode = _open_source_ro(db_path)
        try:
            # The floor the copy must meet, read from the live source while it
            # is open -- a "valid" copy that is missing rows is not a backup.
            expect = _quick_counts(db_path, con=src)
            dst = sqlite3.connect(partial)
            try:
                with dst:
                    src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
        # Never publish an unusable snapshot.
        _verify_snapshot(partial, expect)

        # Compress to a temp name first, then publish: a gzip interrupted
        # mid-stream used to leave a truncated file wearing a final name.
        with open(partial, "rb") as fin, gzip.open(gz_partial, "wb", compresslevel=6) as fout:
            shutil.copyfileobj(fin, fout)
        if os.path.getsize(gz_partial) <= 0:
            raise RuntimeError(f"gzip produced an empty snapshot: {gz_partial}")
        os.replace(gz_partial, dest)
        _remove_db_files(partial)

        # Prune old snapshots of THIS label only (restart snapshots use
        # their own keep, so a busy restart day cannot evict cycle history).
        # Reached only on success: a failure must not cost us good backups.
        keep = keep if keep is not None else _keep_for(label)
        snaps = sorted(
            (f for f in os.listdir(_BACKUP_DIR) if f.startswith(f"atom-{label}-")
             and f.endswith(".db.gz")),
            reverse=True,
        )
        for stale in snaps[keep:]:
            try:
                os.remove(os.path.join(_BACKUP_DIR, stale))
            except OSError:
                pass
        return dest
    except Exception as e:
        # A failed backup must be VISIBLE. This used to log at DEBUG, which is
        # why three consecutive cycles on 2026-09-28 failed unnoticed while
        # protection was silently off: the module whose entire job is to notice
        # trouble was itself failing quietly.
        #
        # Only files THIS run created are removed. Nothing pre-existing is
        # touched, and nothing is pruned.
        for tmp in (partial, gz_partial, raw):
            if os.path.exists(tmp):
                _remove_db_files(tmp)
                logger.warning("removed unpublished snapshot debris: %s", tmp)
        if isinstance(e, sqlite3.Error):
            logger.error(
                "db snapshot (%s) FAILED -- live backup protection is OFF "
                "until this succeeds. sqlite_errorcode=%s sqlite_errorname=%s "
                "type=%s message=%s. Nothing was published and no existing "
                "backup was pruned.",
                label, getattr(e, "sqlite_errorcode", None),
                getattr(e, "sqlite_errorname", None), type(e).__name__, e,
            )
        else:
            logger.error(
                "db snapshot (%s) FAILED -- live backup protection is OFF "
                "until this succeeds. type=%s message=%s. Nothing was "
                "published and no existing backup was pruned.",
                label, type(e).__name__, e,
            )
        return None


def _atomic_write_json(path: str, payload: Dict[str, Any]) -> None:
    """Write JSON so the file is either the old bytes or the new bytes.

    ``open(path, "w")`` truncates FIRST: any error or interrupt between the
    truncate and the end of the dump leaves a 0-byte file. That is not a
    cosmetic problem here -- a 0-byte fingerprint permanently disables wipe
    detection, because ``check_wipe_at_startup`` only re-seeds when the file
    is *absent*, so an empty file is never healed and never overwrites the
    real baseline.

    So: write to a temp file in the same directory, flush, fsync, then
    ``os.replace`` (atomic within a filesystem) into place.
    """
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".fingerprint-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f, indent=1)
            f.flush()
            os.fsync(f.fileno())
        if os.path.getsize(tmp) <= 0:
            raise RuntimeError("refusing to publish an empty fingerprint")
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def load_fingerprint() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Read the fingerprint. Returns ``(fingerprint, problem)``.

    ``problem`` is set when the file exists but cannot be used — empty,
    unparseable, or missing its counts. A file that is *absent* is not a
    problem: that is a genuine first run and the caller may initialize it.
    """
    if not os.path.exists(_FINGERPRINT_PATH):
        return None, None
    try:
        size = os.path.getsize(_FINGERPRINT_PATH)
        if size <= 0:
            return None, f"fingerprint file is empty (0 bytes): {_FINGERPRINT_PATH}"
        with open(_FINGERPRINT_PATH) as f:
            fp = json.load(f)
        if not isinstance(fp, dict) or not (fp.get("counts") or None):
            return None, f"fingerprint file is malformed (no counts): {_FINGERPRINT_PATH}"
        return fp, None
    except Exception as e:
        return None, f"fingerprint file is unreadable: {_FINGERPRINT_PATH}: {e}"


def write_fingerprint() -> Optional[Dict[str, Any]]:
    """Persist current row counts as the known-good world fingerprint.

    Atomic (see ``_atomic_write_json``) and loud on failure: a fingerprint
    that cannot be written means wipe detection is going stale, which is not
    something to log at DEBUG.
    """
    db_path = live_db_path()
    if not db_path or not os.path.exists(db_path):
        return None
    try:
        fp = {
            "counts": _quick_counts(db_path),
            "taken_at": datetime.now(timezone.utc).isoformat(),
        }
        _atomic_write_json(_FINGERPRINT_PATH, fp)
        return fp
    except Exception as e:
        # Was logger.debug, which is why the 2026-09-28 fingerprint sat at
        # 0 bytes all day with nothing in any log.
        logger.error(
            "db fingerprint write FAILED (%s: %s) -- the previous baseline at "
            "%s is being kept unchanged. Wipe detection will be blind once "
            "that baseline goes stale.",
            type(e).__name__, e, _FINGERPRINT_PATH,
        )
        return None


def lance_version_cleanup_step(retention_hours: Optional[float] = None,
                               root: Optional[str] = None) -> Dict[str, Any]:
    """Reclaim LanceDB storage: every table keeps ALL version manifests
    forever unless cleaned, and 2026-09-04 measurements found
    ``documents.lance/_versions`` at 21,998 manifests / 9.9GB — the single
    largest disk consumer on the box (nothing else in the codebase ever
    cleans them).

    Best-effort and fault-isolated per table: opens every ``*.lance`` table
    under ``backend/data/atom_memory/`` and drops version manifests older
    than ``ATOM_LANCE_VERSION_RETENTION_HOURS`` (default 24 — this store
    churns thousands of manifests/day, so a week of them cost ~10GB) plus
    unverified leftovers. The newest manifest and all live data are never
    touched. Runs every maintenance cycle (metadata-only I/O — cheap).
    """
    out: Dict[str, Any] = {"tables": 0, "cleaned": 0, "errors": 0}
    if os.getenv("TESTING") == "1":
        out["reason"] = "testing"
        return out
    if retention_hours is None:
        try:
            retention_hours = float(os.getenv("ATOM_LANCE_VERSION_RETENTION_HOURS", "24"))
        except ValueError:
            retention_hours = 24.0
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    memory_root = root or os.path.join(backend_dir, "data", "atom_memory")
    if not os.path.isdir(memory_root):
        out["reason"] = "no_atom_memory_dir"
        return out

    # Every *.lance directory belongs to the LanceDB connection rooted at
    # its PARENT (a workspace dir may hold several tables).
    tables: Dict[tuple, None] = {}
    for dirpath, _dirnames, _filenames in os.walk(memory_root):
        name = os.path.basename(dirpath)
        if name.endswith(".lance"):
            tables[(os.path.dirname(dirpath), name[: -len(".lance")])] = None

    try:
        import lancedb
    except Exception as e:
        out["reason"] = f"lancedb_unavailable: {e}"
        return out
    from datetime import timedelta

    older_than = timedelta(hours=retention_hours)
    for parent, table in sorted(tables):
        out["tables"] += 1
        try:
            tbl = lancedb.connect(parent).open_table(table)
            # lancedb 0.24: the legacy call survives with `delete_unverified`
            # (the modern path is tbl.optimize(); both land in the same
            # cleanup — keep the legacy one for its CleanupStats return).
            tbl.cleanup_old_versions(older_than=older_than, delete_unverified=True)
            out["cleaned"] += 1
        except Exception as e:
            out["errors"] += 1
            logger.debug(f"lance cleanup skipped {table}: {e}")
    if out["cleaned"]:
        logger.info(
            "lance version cleanup: cleaned %d/%d tables (retention %.0fh)",
            out["cleaned"], out["tables"], retention_hours,
        )
    return out


def maintenance_db_safety_step() -> Dict[str, Any]:
    """The maintenance-cycle step: snapshot + refresh fingerprint. Runs every
    cycle (≈6h) so a wipe is caught at the NEXT startup, not next week."""
    out: Dict[str, Any] = {"snapshot": None, "fingerprint": False}
    snap = snapshot_db("cycle")
    if snap:
        out["snapshot"] = snap
    else:
        # "No snapshot this cycle" must never read as "everything is fine".
        out["snapshot_error"] = "no snapshot was published this cycle"
    out["fingerprint"] = write_fingerprint() is not None
    if not out["fingerprint"]:
        out["fingerprint_error"] = "fingerprint not refreshed this cycle"
    out["protected"] = bool(out["snapshot"]) and out["fingerprint"]
    if not out["protected"]:
        logger.error(
            "db safety cycle INCOMPLETE: snapshot=%s fingerprint=%s -- live "
            "backup protection is degraded until both succeed.",
            bool(out["snapshot"]), out["fingerprint"],
        )
    return out


def check_wipe_at_startup() -> None:
    """Startup comparison of reality vs the maintenance fingerprint. A large
    unexplained drop in agents/users logs a CRITICAL with the restore hint —
    the 2026-09-04 wipe looked like a normal quiet dev DB until someone
    asked where their agent went.

    An empty or malformed fingerprint is a PROTECTION FAILURE, not a first
    run. It is deliberately NOT re-seeded from current counts: writing today's
    numbers over the baseline would make a wipe indistinguishable from a quiet
    day, which is the exact concealment the fingerprint exists to prevent.
    A 0-byte fingerprint from 2026-09-28 is exactly how the wipe net came to
    be silently off while every check returned quietly.
    """
    db_path = live_db_path()
    if not db_path or not os.path.exists(db_path):
        return
    try:
        fp, problem = load_fingerprint()
        if problem is not None:
            preserved = _describe_preserved_baseline()
            logger.critical(
                "DB WIPE DETECTION IS OFF: %s. The dev database at %s is "
                "UNMONITORED -- if a stray script empties it, nothing will "
                "notice. This is NOT re-seeded from current row counts on "
                "purpose: doing so would adopt a wiped database as the new "
                "baseline and hide it. %s Fix the write path, then restore a "
                "known-good baseline by hand (or delete the file and accept "
                "one cycle of no detection). Recent snapshots: %s "
                "(atom-cycle-*.db.gz, atom-pre-restart-*.db.gz).",
                problem, db_path, preserved, _BACKUP_DIR,
            )
            return
        if fp is None:
            # Genuine first run: no file at all. Initializing is correct.
            write_fingerprint()
            return
        known = fp.get("counts") or {}
        current = _quick_counts(db_path)
        known_agents = int(known.get("agent_registry") or 0)
        current_agents = int(current.get("agent_registry") or 0)
        if (
            known_agents >= _FINGERPRINT_MIN_AGENTS
            and current_agents < max(2, known_agents // 2)
        ):
            logger.critical(
                "DB WIPE SUSPECTED: agent_registry fell from %s (fingerprint "
                "%s) to %d at %s — the dev database was likely emptied by a "
                "stray script. Recent snapshots: %s (atom-cycle-*.db, "
                "atom-pre-restart-*.db). The API is still starting; restore "
                "before real work if this was not intentional.",
                known_agents, fp.get("taken_at"), current_agents, db_path,
                _BACKUP_DIR,
            )
    except Exception as e:
        # Also loud: this used to log at DEBUG, so a broken fingerprint meant
        # a silently disabled wipe check.
        logger.error("startup wipe check could not complete (%s: %s) -- the "
                     "dev database is UNMONITORED this startup.",
                     type(e).__name__, e)


def _describe_preserved_baseline() -> str:
    """Name any last-known-good fingerprint we can still point at.

    The 2026-09-28 truncate-before-dump bug destroyed the previous baseline
    outright, so what exists is a CANDIDATE baseline taken from the verified
    backup of 2026-09-28 — a record of what the world looked like that
    afternoon, not a recovered pre-incident baseline. Restoring it is a
    deliberate human decision, never automatic.
    """
    candidate = os.path.join(
        os.path.dirname(_FINGERPRINT_PATH), "incident_20260928",
        "db_fingerprint.candidate_baseline.json")
    try:
        size = os.path.getsize(candidate)
        if size > 0:
            with open(candidate) as f:
                fp = json.load(f)
            if fp.get("counts"):
                return (
                    f"A CANDIDATE baseline is available at {candidate} "
                    f"(taken_at={fp.get('taken_at')}, counts={fp.get('counts')}); "
                    f"it records the world as of that verified backup, not a "
                    f"recovered pre-incident baseline. Copying it into place "
                    f"is a deliberate human decision.")
    except Exception:
        pass
    return ("No preserved baseline is available: the last valid fingerprint "
            "was destroyed by the truncate-before-dump bug. The next "
            "successful write establishes a new one, and until then there is "
            "no comparison point for wipe detection.")
