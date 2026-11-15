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
left untouched. If both files exist, canonical wins and the legacy file is
preserved with a CRITICAL log for an operator decision. Ambiguous sources
(symlink/directory/special file) fail loudly instead of guessing.

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
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy.engine import make_url

from core.local_paths import anchor_sqlite_url

logger = logging.getLogger(__name__)

JOB_STORE_FILE = "jobs.sqlite"


class SchedulerStoreConflict(RuntimeError):
    """An existing scheduler store cannot be adopted without ambiguity."""


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

    Returns a status dict; raises :class:`SchedulerStoreConflict` only when
    the legacy source exists but is ambiguous (symlink/directory/special) or
    when a canonical path is itself not a regular file. Existing canonical and
    legacy files are never overwritten or merged: a conflict is reported for
    an operator to resolve deliberately.

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
            result["status"] = "conflict"
            result["canonical_wins"] = True
            result["legacy_preserved"] = True
            logger.critical(
                "scheduler job store: both canonical (%s) and legacy (%s) "
                "exists; using canonical and preserving legacy untouched. "
                "Operator must decide which store is authoritative.",
                canonical, legacy)
        else:
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

    base.mkdir(parents=True, exist_ok=True)
    temp = canonical.with_name(
        f".{canonical.name}.adopt-{os.getpid()}-{uuid.uuid4().hex}")
    try:
        shutil.copy2(legacy, temp)
        source_sha = _sha256(legacy)
        copied_sha = _sha256(temp)
        if source_sha != copied_sha:
            _conflict(
                f"legacy scheduler store {legacy} changed while being copied; "
                "no adoption was installed")
        try:
            # Exclusive hardlink is atomic and cannot clobber a concurrent
            # canonical file that appeared after the check above.
            os.link(temp, canonical)
        except FileExistsError:
            result["status"] = "conflict"
            result["canonical_wins"] = True
            result["legacy_preserved"] = True
            logger.critical(
                "scheduler job store: canonical %s appeared during legacy "
                "adoption; preserving both files and using canonical", canonical)
            return result
        except OSError:
            # Filesystems without hardlink support: exclusive create + copy.
            fd = os.open(canonical, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "wb") as dest:
                with temp.open("rb") as src:
                    shutil.copyfileobj(src, dest)
            shutil.copystat(legacy, canonical)
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
