"""Canonical SQLite storage for the workflow scheduler's APScheduler jobs.

Why this module exists
----------------------
``core.config.SchedulerConfig`` kept ``job_store_url = "sqlite:///jobs.sqlite"``.
SQLAlchemy resolves that relative file against the process CWD, so launching
the backend from the repo root and from ``backend/`` pointed the scheduler at
two different job stores. Jobs scheduled in one launch silently disappeared
in the other.

The resolver below reuses the repo's canonical SQLite URL anchoring
(``core.local_paths.anchor_sqlite_url``, already used by
``core.database.get_database_url``) so the default store is always
``<backend>/jobs.sqlite`` — the ordinary backend-launch location — regardless
of CWD. It is applied at scheduler construction, not at configuration import,
so importing/testing config never creates or moves a store.

Legacy adoption
---------------
Before this fix, a root-launch wrote ``<repo>/jobs.sqlite``. On the first
startup that uses the canonical store, ``reconcile_scheduler_job_store``
adopts that legacy file when (and only when) the canonical file is absent and
the source is an unambiguous regular file. The copy is byte-verified and
created with an exclusive hardlink (no overwrite possible); the original is
left untouched. If both files exist, automatic selection is refused and both
are preserved for an explicit operator decision. Ambiguous sources
(symlink/directory/special file), uncheckpointed WAL/SHM sidecars and
filesystems without atomic hardlinks fail loudly instead of guessing or
publishing a partial canonical file.

This is intentionally a one-store, one-file reconciliation, not a migration
framework. It runs only from the backend startup path immediately before the
scheduler starts, never from ``SchedulerConfig.__post_init__`` or module
import.
"""
from __future__ import annotations

import errno
import hashlib
import logging
import os
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy.engine import make_url

from core.local_paths import anchor_sqlite_url

logger = logging.getLogger(__name__)

JOB_STORE_FILE = "jobs.sqlite"
# Appended to the resolved store filename to form the sibling lock sidecar.
JOB_STORE_LOCK_SUFFIX = ".lock"


class SchedulerStoreConflict(RuntimeError):
    """An existing scheduler store cannot be adopted without ambiguity."""


class SchedulerStoreUnavailable(RuntimeError):
    """The process knows its scheduler storage is unsafe / not authoritative.

    Raised by scheduler mutators/readers (and therefore by the schedule/list/
    remove consumers) so a refused startup can never acknowledge a RAM-only
    pending job or present an empty store as authoritative.
    """


class SchedulerStoreLockError(RuntimeError):
    """The scheduler store ownership lock could not be managed."""


class SchedulerStoreLockUnsupported(SchedulerStoreLockError):
    """The scheduler store cannot use a same-host filesystem lock.

    Raised for non-SQLite backends, in-memory SQLite URLs and SQLite ``file:``
    URI databases, which have no stable on-disk sibling for the sidecar.
    """


class SchedulerStoreLockContended(SchedulerStoreLockError):
    """Another process already holds the scheduler store ownership lock."""


_STORE_STATE_LOCK = threading.Lock()
# None = unverified (component/pre-start use); True = verified ready;
# False = known unsafe (conflict, failed adoption, failed start).
_STORE_STATE: Dict[str, Any] = {"ready": None, "reason": None}


def mark_scheduler_store_ready() -> None:
    with _STORE_STATE_LOCK:
        _STORE_STATE["ready"] = True
        _STORE_STATE["reason"] = None


def mark_scheduler_store_failed(reason: str) -> None:
    with _STORE_STATE_LOCK:
        _STORE_STATE["ready"] = False
        _STORE_STATE["reason"] = str(reason or "scheduler storage is unavailable")


def reset_scheduler_store_state() -> None:
    """Test seam: return to the unverified (component/pre-start) state."""
    with _STORE_STATE_LOCK:
        _STORE_STATE["ready"] = None
        _STORE_STATE["reason"] = None


def scheduler_store_state() -> Dict[str, Any]:
    with _STORE_STATE_LOCK:
        return dict(_STORE_STATE)


def require_scheduler_store_ready() -> None:
    """Refuse scheduler operations only when storage is KNOWN unsafe."""
    state = scheduler_store_state()
    if state.get("ready") is False:
        raise SchedulerStoreUnavailable(
            state.get("reason") or "Scheduler storage is unavailable")


def backend_root() -> Path:
    """The documented backend launch root (``.../backend``)."""
    return Path(__file__).resolve().parents[1]


def canonical_job_store_path(root: Path | str | None = None) -> Path:
    return Path(root) / JOB_STORE_FILE if root is not None else backend_root() / JOB_STORE_FILE


def legacy_job_store_path(root: Path | str | None = None) -> Path:
    """Old CWD-relative location from a repo-root launch."""
    base = Path(root) if root is not None else backend_root()
    return base.parent / JOB_STORE_FILE


def resolve_scheduler_job_store_url(
    url: str, root: Path | str | None = None,
) -> str:
    """Resolve the effective APScheduler SQLAlchemy URL.

    Relative SQLite file paths anchor to ``backend/``. Absolute paths,
    ``:memory:``, ``file:`` URIs are returned unchanged. A driver-less
    PostgreSQL URL is pinned to the declared ``psycopg2`` driver (SQLAlchemy
    2.1 defaults to psycopg3, which this install does not ship); explicit
    drivers and all non-PostgreSQL/non-SQLite URLs pass through unchanged.
    """
    from core.local_paths import normalize_postgres_driver

    return normalize_postgres_driver(anchor_sqlite_url(url, root))


def _sqlite_file_path(url: str) -> Optional[Path]:
    """Filesystem path of a SQLite file URL, or None for non-file forms."""
    try:
        parsed = make_url(url)
    except Exception:
        return None
    if parsed.get_backend_name() != "sqlite":
        return None
    database = parsed.database
    if not database or database == ":memory:" or database.startswith("file:"):
        return None
    return Path(database)


def _safe_url(url: Optional[str]) -> str:
    """URL for logs/evidence with any password removed."""
    if not url:
        return ""
    try:
        return make_url(url).render_as_string(hide_password=True)
    except Exception:
        return "<unparseable-url>"


def _ownership_lock_paths(
    url: Optional[str], root: Path | str | None,
) -> tuple[Path, Path]:
    """Resolve the on-disk store path and its stable sibling lock sidecar.

    Uses the same canonical URL anchoring as
    :func:`reconcile_scheduler_job_store` and the same SQLite-file
    classification as ``_sqlite_file_path``. Raises
    :class:`SchedulerStoreLockUnsupported` for anything without a persistent
    on-disk SQLite file. Error messages intentionally include no URL text, so
    an unsupported backend's credentials cannot be echoed by this primitive.
    """
    if url is None:
        from core.config import get_config

        url = get_config().scheduler.job_store_url

    base = Path(root) if root is not None else backend_root()
    try:
        effective = resolve_scheduler_job_store_url(url, base)
    except Exception:
        raise SchedulerStoreLockUnsupported(
            "scheduler ownership lock could not resolve the configured "
            "scheduler store URL; a persistent on-disk SQLite URL is required"
        ) from None
    path = _sqlite_file_path(effective)
    if path is None:
        try:
            parsed = make_url(effective)
        except Exception:
            raise SchedulerStoreLockUnsupported(
                "scheduler ownership lock requires a parseable SQLite URL; "
                "the configured scheduler store URL could not be parsed"
            ) from None
        backend = parsed.get_backend_name()
        database = parsed.database
        if backend != "sqlite":
            raise SchedulerStoreLockUnsupported(
                "scheduler ownership lock supports only persistent on-disk "
                f"SQLite stores; the configured backend is {backend!r}"
            ) from None
        if not database or database == ":memory:":
            raise SchedulerStoreLockUnsupported(
                "scheduler ownership lock requires a persistent on-disk "
                "SQLite store; the configured URL is an in-memory database"
            ) from None
        raise SchedulerStoreLockUnsupported(
            "scheduler ownership lock does not support SQLite URI (file:) "
            "databases; configure a plain filesystem path"
        ) from None

    try:
        store_path = path.resolve(strict=True)
    except FileNotFoundError:
        # Permit only a genuinely new final plain filename. Broken/cyclic final
        # symlinks are not plain filenames, and the parent must fully resolve.
        if path.is_symlink() or path.name in ("", ".", ".."):
            raise SchedulerStoreLockError("invalid scheduler store path") from None
        try:
            parent_path = path.parent.resolve(strict=True)
        except (OSError, RuntimeError):
            raise SchedulerStoreLockError("invalid scheduler store path") from None
        store_path = parent_path / path.name
    except (OSError, RuntimeError):
        # Broken/cyclic symlinks and unresolvable parents must never acquire a lock.
        raise SchedulerStoreLockError("invalid scheduler store path") from None
    else:
        # Defensive check for interpreters that fail to raise on a self-referential
        # final symlink during strict resolution.
        if not path.exists():
            raise SchedulerStoreLockError("invalid scheduler store path") from None
    lock_path = store_path.with_name(store_path.name + JOB_STORE_LOCK_SUFFIX)
    return store_path, lock_path


class SchedulerStoreOwnershipLock:
    """Exclusive same-host ownership lock for a persistent SQLite job store.

    This is an opt-in runtime primitive. It never creates, reconciles or
    mutates the job store, and nothing in this module acquires it implicitly.

    Lifecycle
    ---------
    * Construct with the scheduler's job-store URL (and the same optional
      ``root`` test seam used by the reconciler). Construction resolves and
      validates the URL but performs no filesystem writes.
    * :meth:`acquire` opens/creates ``<store>.lock`` next to the store, takes
      a nonblocking exclusive POSIX ``flock`` and keeps that descriptor open.
      The lock is held until :meth:`release` (or ``__exit__``) closes it.
    * :meth:`acquire` is not reentrant on one instance. A competing owner
      raises :class:`SchedulerStoreLockContended`; other open/flock failures
      raise :class:`SchedulerStoreLockError`. The descriptor is closed before
      any acquisition failure escapes.
    * :meth:`release` unlocks and closes the descriptor but deliberately never
      unlinks ``<store>.lock``. Unlinking would let a later process create a
      new inode at the same path while an earlier waiter still holds the old
      one, defeating mutual exclusion.
    * The returned object must be kept alive for the ownership period. Use it
      as a context manager, or call :meth:`release` explicitly.

    Limitations
    -----------
    * Same-host only: ``flock`` is not a reliable cross-host or NFS lock.
    * Advisory only: processes that do not use this primitive are not blocked,
      and SQLite's own locking is a separate mechanism.
    * It coordinates scheduler ownership, not store reconciliation or job
      execution; startup wiring is intentionally out of scope here.
    * The sidecar may be created empty and is intentionally left behind.
    * External deletion/replacement of the sidecar can defeat exclusion; this
      primitive itself never unlinks it.
    * The open descriptor is inherited across ``fork``; child processes should
      release it or avoid forking while ownership is held.
    * POSIX only: platforms without ``fcntl.flock`` are rejected explicitly.
    """

    def __init__(
        self, url: Optional[str] = None, *,
        root: Path | str | None = None,
    ) -> None:
        self._store_path, self._lock_path = _ownership_lock_paths(url, root)
        self._fd: Optional[int] = None

    @property
    def store_path(self) -> Path:
        """Canonical on-disk SQLite store this lock protects."""
        return self._store_path

    @property
    def lock_path(self) -> Path:
        """Stable sibling sidecar used for the ``flock``; never unlinked."""
        return self._lock_path

    @property
    def is_held(self) -> bool:
        """Whether this object currently holds an open lock descriptor."""
        return self._fd is not None

    def acquire(self) -> "SchedulerStoreOwnershipLock":
        """Take the nonblocking exclusive lock, returning ``self``.

        Raises :class:`SchedulerStoreLockContended` when another process owns
        the store and :class:`SchedulerStoreLockError` for other failures.
        """
        if self._fd is not None:
            raise SchedulerStoreLockError(
                f"scheduler ownership lock {self._lock_path} is already held "
                "by this object")
        try:
            import fcntl
        except ImportError:
            raise SchedulerStoreLockUnsupported(
                "scheduler ownership locks require POSIX fcntl.flock, which "
                "is unavailable on this platform") from None

        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0)
        fd: Optional[int] = None
        try:
            fd = os.open(os.fspath(self._lock_path), flags, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise SchedulerStoreLockContended(
                    f"scheduler job store {self._store_path} is already owned "
                    f"(lock {self._lock_path} is held by another owner)"
                ) from None
            except OSError as exc:
                if exc.errno in (errno.EACCES, errno.EAGAIN,
                                 errno.EWOULDBLOCK):
                    raise SchedulerStoreLockContended(
                        f"scheduler job store {self._store_path} is already "
                        "owned (lock "
                        f"{self._lock_path} is held by another owner)"
                    ) from None
                raise SchedulerStoreLockError(
                    "could not acquire scheduler ownership lock "
                    f"{self._lock_path}: {exc.strerror or exc}") from None
        except SchedulerStoreLockError:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            raise
        except OSError as exc:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            raise SchedulerStoreLockError(
                "could not open scheduler ownership lock "
                f"{self._lock_path}: {exc.strerror or exc}") from None

        self._fd = fd
        logger.info(
            "scheduler job store: acquired ownership lock %s for %s",
            self._lock_path, self._store_path)
        return self

    def release(self) -> None:
        """Unlock and close the descriptor; never unlink the sidecar inode."""
        fd, self._fd = self._fd, None
        if fd is None:
            return
        try:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError as exc:
            logger.warning(
                "scheduler job store: explicit unlock of %s failed (%s); "
                "closing the descriptor still releases it",
                self._lock_path, exc.strerror or exc)
        finally:
            try:
                os.close(fd)
            except OSError as exc:
                logger.warning(
                    "scheduler job store: closing ownership lock descriptor "
                    "for %s failed (%s)",
                    self._lock_path, exc.strerror or exc)
        logger.info(
            "scheduler job store: released ownership lock %s for %s",
            self._lock_path, self._store_path)
        # Deliberately no unlink here. The inode is the lock identity: removing
        # it would let a new process lock a fresh inode at the same path while
        # an existing waiter still holds the old one.

    def __enter__(self) -> "SchedulerStoreOwnershipLock":
        return self.acquire()

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        self.release()
        return False


def acquire_scheduler_store_ownership_lock(
    url: Optional[str],
    *,
    root: Path | str | None = None,
) -> SchedulerStoreOwnershipLock:
    return SchedulerStoreOwnershipLock(url, root=root).acquire()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _conflict(message: str) -> None:
    logger.critical("scheduler job store: %s", message)
    raise SchedulerStoreConflict(message)


def reconcile_scheduler_job_store(
    url: Optional[str] = None,
    *,
    root: Path | str | None = None,
    legacy_root: Path | str | None = None,
) -> Dict[str, Any]:
    """Adopt a legacy repo-root ``jobs.sqlite`` into the canonical store.

    Returns a status dict; raises :class:`SchedulerStoreConflict` when both
    stores exist, the legacy source is ambiguous (symlink/directory/special or
    has -wal/-shm sidecars), a canonical path is not a regular file, copying
    fails, or the filesystem cannot install the store with an atomic
    no-clobber hardlink. Existing files are never overwritten or merged; both
    are preserved for an operator to resolve deliberately.

    ``root``/``legacy_root`` are test seams (synthetic backend/legacy roots);
    production callers use the backend anchor.
    """
    if url is None:
        from core.config import get_config

        url = get_config().scheduler.job_store_url
    base = Path(root) if root is not None else backend_root()
    canonical = canonical_job_store_path(base)
    legacy = (Path(legacy_root) / JOB_STORE_FILE
              if legacy_root is not None else legacy_job_store_path(base))

    effective = resolve_scheduler_job_store_url(url, base)
    path = _sqlite_file_path(effective)
    result: Dict[str, Any] = {
        "configured_url": _safe_url(url),
        "effective_url": _safe_url(effective),
        "canonical_path": str(canonical),
        "legacy_path": str(legacy),
        "status": "not_sqlite_file",
    }
    if path is None:
        return result
    try:
        same_store = path.resolve(strict=False) == canonical.resolve(strict=False)
    except OSError:
        same_store = False
    if not same_store:
        result["status"] = "not_canonical"
        return result

    if canonical.is_symlink() or (canonical.exists() and not canonical.is_file()):
        _conflict(
            f"canonical path {canonical} exists but is not a regular file; "
            "refusing to replace it")
    if canonical.exists():
        if legacy.exists() or legacy.is_symlink():
            _conflict(
                f"both canonical ({canonical}) and legacy ({legacy}) scheduler "
                "stores exist; refusing automatic selection so neither can be "
                "silently hidden. Both files are preserved; an operator must "
                "choose which store is authoritative")
        result["status"] = "canonical_present"
        return result

    if legacy.is_symlink():
        _conflict(
            f"legacy scheduler store {legacy} is a symlink; refusing to "
            "adopt an ambiguous source")
    if legacy.exists() and not legacy.is_file():
        _conflict(
            f"legacy scheduler store {legacy} is not a regular file; "
            "refusing to adopt an ambiguous source")
    if not legacy.exists():
        result["status"] = "fresh"
        return result

    # A live/uncheckpointed SQLite store may keep recent transactions in
    # -wal/-shm sidecars. Copying only the main file would silently lose
    # them; require the old process to be stopped and checkpointed first.
    sidecars = [Path(str(legacy) + suffix)
                for suffix in ("-wal", "-shm", "-journal")]
    present_sidecars = [str(path) for path in sidecars
                        if path.exists() or path.is_symlink()]
    if present_sidecars:
        _conflict(
            f"legacy scheduler store {legacy} has SQLite sidecar(s) "
            f"{present_sidecars}; stop the old backend and checkpoint/close "
            "the store before adopting it")

    base.mkdir(parents=True, exist_ok=True)
    temp = canonical.with_name(
        f".{canonical.name}.adopt-{os.getpid()}-{uuid.uuid4().hex}")
    try:
        try:
            shutil.copy2(legacy, temp)
        except OSError as exc:
            _conflict(
                f"copying legacy scheduler store {legacy} failed ({exc}); "
                "no canonical file was published")
        source_sha = _sha256(legacy)
        copied_sha = _sha256(temp)
        if source_sha != copied_sha:
            _conflict(
                f"legacy scheduler store {legacy} changed while being copied; "
                "no adoption was installed")
        # Close the writer race: a writer may have opened the store after the
        # pre-copy sidecar check. Never install a snapshot while a journal/WAL
        # is active.
        post_sidecars = [str(path) for path in sidecars
                         if path.exists() or path.is_symlink()]
        if post_sidecars:
            _conflict(
                f"legacy scheduler store {legacy} became active during "
                f"adoption (sidecar(s) {post_sidecars}); no canonical file "
                "was published")
        try:
            # Exclusive hardlink is the only install primitive used: it is
            # atomic and cannot clobber a concurrent canonical file. There is
            # deliberately NO direct-write fallback, because a disk-full error
            # mid-copy would publish a partial canonical store and the next
            # startup would hide the intact legacy file.
            os.link(temp, canonical)
        except FileExistsError:
            _conflict(
                f"canonical {canonical} appeared during legacy adoption; "
                "refusing automatic selection and preserving both files")
        except OSError as exc:
            _conflict(
                f"filesystem cannot install the legacy scheduler store "
                f"atomically (no-clobber hardlink failed: {exc}); refusing "
                "adoption rather than publishing a partial canonical file")
        logger.warning(
            "scheduler job store: ADOPTED legacy %s into canonical %s "
            "(sha256=%s); original preserved untouched",
            legacy, canonical, source_sha)
        result.update({
            "status": "adopted",
            "source_sha256": source_sha,
            "canonical_sha256": _sha256(canonical),
            "original_preserved": True,
        })
        return result
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def reconcile_and_mark_scheduler_store(
    url: Optional[str] = None, *,
    root: Path | str | None = None,
    legacy_root: Path | str | None = None,
) -> Dict[str, Any]:
    """Startup helper: reconcile then publish shared ready/failed state.

    Any refusal (conflict, ambiguous/WAL source, unsupported atomic install,
    copy failure) marks the process state failed before re-raising, so the
    scheduler methods and their consumers cannot acknowledge RAM-only jobs or
    present an empty store as authoritative. A successful no-op/adoption
    marks the store ready. Never called from config construction/import.
    """
    try:
        result = reconcile_scheduler_job_store(
            url, root=root, legacy_root=legacy_root)
    except Exception as exc:
        mark_scheduler_store_failed(str(exc))
        raise
    mark_scheduler_store_ready()
    return result


def scheduler_job_store_status(
    url: Optional[str] = None, *,
    root: Path | str | None = None,
    legacy_root: Path | str | None = None,
) -> Dict[str, Any]:
    """Read-only store state for logs/diagnostics (no adoption)."""
    base = Path(root) if root is not None else backend_root()
    canonical = canonical_job_store_path(base)
    legacy = (Path(legacy_root) / JOB_STORE_FILE
              if legacy_root is not None else legacy_job_store_path(base))
    effective = resolve_scheduler_job_store_url(
        url if url is not None else "sqlite:///jobs.sqlite", base)
    return {
        "configured_url": _safe_url(url),
        "effective_url": _safe_url(effective),
        "canonical_path": str(canonical),
        "canonical_present": canonical.is_file(),
        "legacy_path": str(legacy),
        "legacy_present": legacy.is_file(),
        "legacy_is_symlink": legacy.is_symlink(),
    }
