"""Cross-process advisory locks for LanceDB table mutations.

LanceDB's in-process locks (``LanceDBHandler._write_lock``) only serialize
threads inside ONE interpreter.  The re-embed migration replaces a whole
table with a single ``mode="overwrite"`` commit, so a second OS process that
appends (or deletes) between the migration's final live read and that commit
is silently erased — verified with a two-process probe: process B's
``add_document`` returned True and B could read its own row, but the commit
that landed afterwards (built from A's snapshot) contained only A's rows.

The filesystem lock in this module closes that gap for the deployment this
repo documents: a local LanceDB directory (``backend/data/atom_memory``,
optionally behind a symlink to the portable drive).  Every handler mutation
takes it, so no participating process can commit inside another process's
read→overwrite window.

Design notes
------------
* ``flock``/``msvcrt`` advisory locks are tied to the open file description
  and are released by the kernel when the process exits — a crashed writer
  cannot leave a stale lock behind (unlike a lock *directory*).
* The lock file lives in a sibling directory (``<store>.atom-write-locks``),
  never inside the Lance dataset, so ``table_names()`` and dataset discovery
  are unaffected.
* Lock identity is ``(realpath(store), table)``.  Two processes that reach
  the same store through different relative paths or a symlink converge on
  the same lock file; two genuinely different stores never contend.
* This is an advisory lock.  Code that mutates a table through a raw
  ``lancedb.connect()`` handle instead of ``LanceDBHandler`` must take this
  lock explicitly (the communication ingestion pipeline does; its table can be
  migrated by the handler).  Read-only raw connections need no lock.

Storage topology limits (why this is local-FS only)
---------------------------------------------------
``flock`` coordinates processes that see the same inode.  It cannot
coordinate separate hosts (S3/GCS/Azure/``db://`` object stores), and a
network filesystem must provide working advisory locking.  On a non-local
URI ``process_table_write_lock`` therefore yields ``False`` and the caller
decides: ordinary writes proceed (best effort, as before), while the
re-embed swap must refuse to overwrite (there is no supported shared commit
protocol).  A genuinely distributed store needs a distributed commit lock
(Lance's ``commit_lock`` hook backed by DynamoDB/Redis/etc.); this
repository does not ship one.

Fail-closed on local stores
---------------------------
For a local store the lock is NOT best effort: if the lock file cannot be
created or the OS lock cannot be acquired, ``process_table_write_lock``
raises :class:`WriteLockUnavailable` without yielding, and the caller's
mutation never runs.  Silently continuing would let a writer commit inside a
re-embed's read→overwrite window — the exact lost-write bug this module
exists to prevent.  Nested guarded calls reuse the outer acquisition (the
OS lock is per open file description, so a second ``flock`` from the same
process would deadlock); a nested call under a *failed* guard therefore
fails too, never falling through to an unguarded mutation.

Only two cases still yield ``False``:
* a non-local store (no lock exists to take — ordinary writes stay
  best-effort, as before), and
* a local store directory that does not exist yet (no dataset can be lost;
  ``LanceDBHandler._ensure_db`` creates the store before writing).
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import os
import re
import threading
import time
from typing import Iterator, Optional

logger = logging.getLogger(__name__)


class WriteLockUnavailable(RuntimeError):
    """The exclusive write lock for a LOCAL store could not be acquired.

    Raised before the guarded mutation runs, so a caller can report failure
    (its usual ``except Exception`` path) without touching the dataset.
    """

try:  # POSIX
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None

try:  # Windows
    import msvcrt
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None


#: URI schemes that are not backed by a filesystem this process can lock.
_REMOTE_STORE_PREFIXES = (
    "s3://",
    "s3a://",
    "gs://",
    "gcs://",
    "az://",
    "azure://",
    "abfs://",
    "abfss://",
    "db://",
    "memory://",
)


def is_local_store(db_path: str) -> bool:
    """True when ``db_path`` is a local directory we can lock on the FS."""
    if not db_path:
        return False
    return not str(db_path).lower().startswith(_REMOTE_STORE_PREFIXES)


def store_identity(db_path: str) -> str:
    """Canonical identity for a store path (symlinks and CWD resolved).

    ``_resolve_local_db_path`` already anchors relative paths to ``backend/``;
    ``realpath`` additionally makes a store reached through the portable-drive
    symlink and through its real location share one lock namespace.
    """
    return os.path.realpath(os.path.abspath(os.path.expanduser(db_path)))


def lock_directory(db_path: str) -> str:
    """Sibling directory holding this store's lock files."""
    return store_identity(db_path) + ".atom-write-locks"


def _safe_table_stem(table_name: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(table_name))[:80] or "table"
    digest = hashlib.sha1(str(table_name).encode("utf-8")).hexdigest()[:12]
    # The digest makes the name collision-free even when sanitisation maps
    # two different table names to the same stem.
    return f"{stem}-{digest}.lock"


def lock_file_path(db_path: str, table_name: str) -> str:
    return os.path.join(lock_directory(db_path), _safe_table_stem(table_name))


# In-process companions to the OS lock.  The OS lock is held per process, so
# threads inside one process would not exclude each other; this RLock does,
# and the depth counter makes nesting (a writer calling another guarded
# mutation) safe without releasing the OS lock early.
_THREAD_LOCKS: dict[tuple, "threading.RLock"] = {}
_THREAD_LOCK_DEPTH: dict[tuple, int] = {}
_THREAD_LOCK_HELD: dict[tuple, bool] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


def _thread_lock(key: tuple) -> "threading.RLock":
    with _THREAD_LOCKS_GUARD:
        lock = _THREAD_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _THREAD_LOCKS[key] = lock
        return lock


@contextlib.contextmanager
def process_table_write_lock(
    db_path: str,
    table_name: str,
    *,
    fail_closed: Optional[bool] = None,
) -> Iterator[bool]:
    """Hold the cross-process exclusive lock for ``(store, table)``.

    Reentrant within a process/thread: a guarded mutation that calls another
    guarded mutation on the same table keeps one OS lock and one depth count
    (a second ``flock`` on a fresh fd from the same process would deadlock).

    Yields ``True`` when an OS-level lock is held.  Yields ``False`` only when
    there is no lock to take: a non-local store, or a local store directory
    that does not exist yet (nothing to protect).  For a local store an
    acquisition failure **raises** :class:`WriteLockUnavailable` instead of
    yielding, so the caller cannot proceed to mutate without exclusivity.
    ``fail_closed`` overrides the default (``True`` for local stores,
    ``False`` for non-local ones).
    """
    local = is_local_store(db_path)
    store = store_identity(db_path) if local else str(db_path)
    key = (store, str(table_name))
    required = local if fail_closed is None else bool(fail_closed)
    with _thread_lock(key):
        if _THREAD_LOCK_DEPTH.get(key, 0) > 0:
            held = _THREAD_LOCK_HELD.get(key, False)
            if required and not held:
                # A nested call must never turn a failed/absent outer guard
                # into an unguarded mutation.
                raise WriteLockUnavailable(
                    f"no exclusive write lock held for '{table_name}' in "
                    f"{db_path}; refusing nested mutation"
                )
            _THREAD_LOCK_DEPTH[key] += 1
            try:
                yield held
            finally:
                _THREAD_LOCK_DEPTH[key] -= 1
            return

        if not local:
            if required:
                raise WriteLockUnavailable(
                    f"store {db_path} is not a local filesystem; no exclusive "
                    f"write lock can be taken for '{table_name}'"
                )
            yield False
            return

        if not os.path.isdir(store):
            # Nothing to protect yet (the handler creates the store on
            # connect, before any mutation).  Avoid littering lock directories
            # beside a store that does not exist — e.g. tests that mock the DB.
            yield False
            return

        path = lock_file_path(db_path, table_name)
        fd = None
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"\0")
            _acquire(fd)
        except Exception as exc:  # noqa: BLE001 - classified just below
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if required:
                # Fail closed: a local writer must not commit while another
                # process may be inside its re-embed read→overwrite window.
                logger.error(
                    "Refusing write to '%s' in %s: cross-process write lock "
                    "unavailable (%s)",
                    table_name,
                    db_path,
                    exc,
                )
                raise WriteLockUnavailable(
                    f"cross-process write lock unavailable for '{table_name}' "
                    f"in {db_path}: {exc}"
                ) from exc
            logger.warning(
                "Cross-process write lock unavailable for '%s' in %s: %s "
                "(non-local store; writes continue best effort)",
                table_name,
                db_path,
                exc,
            )
            yield False
            return

        _THREAD_LOCK_DEPTH[key] = 1
        _THREAD_LOCK_HELD[key] = True
        try:
            yield True
        finally:
            _THREAD_LOCK_DEPTH[key] = 0
            _THREAD_LOCK_HELD[key] = False
            try:
                _release(fd)
            finally:
                try:
                    os.close(fd)
                except OSError:
                    pass


def _acquire(fd: int) -> None:
    if fcntl is not None:
        fcntl.flock(fd, fcntl.LOCK_EX)
        return
    if msvcrt is not None:  # pragma: no cover - Windows
        os.lseek(fd, 0, os.SEEK_SET)
        while True:
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                time.sleep(0.05)
    raise RuntimeError("no advisory file-lock implementation available")


def _release(fd: int) -> None:
    try:
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_UN)
        elif msvcrt is not None:  # pragma: no cover - Windows
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    except OSError:  # closing the fd releases the lock anyway
        pass
