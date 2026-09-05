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
import logging
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Optional

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


def _quick_counts(db_path: str) -> Dict[str, int]:
    """Best-effort row counts (missing tables count 0 — a wiped DB may not
    even have them yet)."""
    counts: Dict[str, int] = {}
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        for table in _COUNT_TABLES:
            try:
                counts[table] = con.execute(
                    f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.OperationalError:
                counts[table] = 0
    finally:
        con.close()
    return counts


def snapshot_db(label: str = "cycle", keep: Optional[int] = None) -> Optional[str]:
    """WAL-safe backup of the live sqlite DB into backend/data/backups/,
    gzipped (sqlite text compresses ~4x; the box is disk-constrained).

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
    try:
        free = shutil.disk_usage(db_path).free
        if free < _min_free_bytes():
            logger.warning(
                "db snapshot skipped: only %.0f MB free (floor %s MB) — "
                "free disk space or lower ATOM_DB_SNAPSHOT_MIN_FREE_MB",
                free / 1024 / 1024,
                os.getenv("ATOM_DB_SNAPSHOT_MIN_FREE_MB", "500"),
            )
            return None

        os.makedirs(_BACKUP_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = os.path.join(_BACKUP_DIR, f"atom-{label}-{ts}.db.gz")
        src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        raw = dest[:-3]  # strip .gz for the sqlite backup target
        try:
            dst = sqlite3.connect(raw)
            try:
                with dst:
                    src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
        with open(raw, "rb") as fin, gzip.open(dest, "wb", compresslevel=6) as fout:
            shutil.copyfileobj(fin, fout)
        os.remove(raw)

        # Prune old snapshots of THIS label only (restart snapshots use
        # their own keep, so a busy restart day cannot evict cycle history).
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
        logger.debug(f"db snapshot ({label}) skipped: {e}")
        return None


def write_fingerprint() -> Optional[Dict[str, Any]]:
    """Persist current row counts as the known-good world fingerprint."""
    db_path = live_db_path()
    if not db_path or not os.path.exists(db_path):
        return None
    try:
        fp = {
            "counts": _quick_counts(db_path),
            "taken_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(_FINGERPRINT_PATH, "w") as f:
            json.dump(fp, f, indent=1)
        return fp
    except Exception as e:
        logger.debug(f"db fingerprint write skipped: {e}")
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
    out["fingerprint"] = write_fingerprint() is not None
    return out


def check_wipe_at_startup() -> None:
    """Startup comparison of reality vs the maintenance fingerprint. A large
    unexplained drop in agents/users logs a CRITICAL with the restore hint —
    the 2026-09-04 wipe looked like a normal quiet dev DB until someone
    asked where their agent went."""
    db_path = live_db_path()
    if not db_path or not os.path.exists(db_path):
        return
    try:
        if not os.path.exists(_FINGERPRINT_PATH):
            write_fingerprint()
            return
        with open(_FINGERPRINT_PATH) as f:
            fp = json.load(f)
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
        logger.debug(f"startup wipe check skipped: {e}")
