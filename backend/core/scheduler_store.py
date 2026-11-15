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


class SchedulerStoreConflict(RuntimeError):
    """An existing scheduler store cannot be adopted without ambiguity."""


class SchedulerStoreUnavailable(RuntimeError):
    """The process knows its scheduler storage is unsafe / not authoritative.

    Raised by scheduler mutators/readers (and therefore by the schedule/list/
    remove consumers) so a refused startup can never acknowledge a RAM-only
    pending job or present an empty store as authoritative.
    """


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
    ``:memory:``, ``file:`` URIs and non-SQLite URLs are returned unchanged.
    """
    return anchor_sqlite_url(url, root)


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
    sidecars = [Path(str(legacy) + suffix) for suffix in ("-wal", "-shm")]
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
