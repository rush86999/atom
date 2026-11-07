"""Manifest-verified local SQLite backup restore for the existing release kit.

This module is deliberately part of the existing assignment-successor kit.  It
reuses the kit's ``BACKUP_MANIFEST.json`` schema and its SQLite backup/verify
discipline; it is not a second backup engine, store, API, or UI.

Primary practice used here:
- SQLite backup API gives a consistent snapshot including committed WAL:
  https://www.sqlite.org/backup.html
- The destination must be a separate connection; we never byte-copy a live
  database or its WAL/SHM:
  https://www.sqlite.org/c3ref/backup_finish.html
- Staging + no-replace publication and explicit copy/symlink checks follow
  Python's documented ``shutil``/``os`` semantics:
  https://docs.python.org/3.14/library/shutil.html
  https://docs.python.org/3/library/os.html

The restore is intentionally conservative:

* The manifest is validated once, and the database copy is bound to the exact
  bytes that were validated.  We freeze those already-checkpointed backup bytes
  through a ``O_NOFOLLOW`` file descriptor into a private staging directory,
  verify size/hash/file identity again, and only then run the SQLite backup API
  on the frozen image.  A peer changing the backup file after validation cannot
  be published.
* Historical audit material is immutable.  Current writable projections may be
  rebased, and a new restore-owned ``CanvasAudit`` event is appended with its
  own id and provenance.  Original audit ids, actors, timestamps, material and
  operation identities are never rewritten.
"""
from __future__ import annotations

import contextvars
import ctypes
import errno
import hashlib
import json
import os
import posixpath
import re
import shutil
import sqlite3
import stat as stat_module
import sys
import tempfile
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import quote

SCHEMA = "atom-assignment-release-backup-1"
DB_NAME = "atom.db"
DB_SIDECARS = {"atom.db-wal", "atom.db-shm", "atom.db-journal"}
MANAGED_DIRS = ("office", "sheet_datasets", "email_attachments", "atom_memory")
KNOWN_TOP_LEVEL = {
    DB_NAME, *DB_SIDECARS, *MANAGED_DIRS,
    "byok_config.json", "byok_keys.json", "byok_encryption_key", "config",
}
CREDENTIAL_PREFIXES = ("byok_",)
ALLOWED_MEMORY_SCHEMES = ("", "file")
_ROW_COUNT_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
_RESTORE_ACTION = "restore"

# The real flow sets this before calling ``_copy_database``.  It is a
# contextvar (not a global) so concurrent restores in one process cannot bind
# each other to the wrong manifest.  ``_copy_database`` also accepts an
# explicit ``expected`` keyword; the contextvar exists so test wrappers that
# call the original three-argument function still get the manifest binding.
_ACTIVE_DB_BINDING: contextvars.ContextVar[Optional[Dict[str, Any]]] = (
    contextvars.ContextVar("atom_restore_active_db_binding", default=None)
)

# Test-only seams.  Production never sets these; they let tests force a source
# change during a read or a peer creation immediately before publication.
_READ_HOOK: Optional[Callable[[Path, int], None]] = None
_PUBLISH_HOOK: Optional[Callable[[Path], None]] = None


class BackupConfigError(RuntimeError):
    """The configured backup source roots are ambiguous or unsupported."""


class RestoreRefused(RuntimeError):
    """The restore refused before publishing anything to the target."""


class RestoreUncertain(RuntimeError):
    """The target was published but could not be independently re-verified."""


def sqlite_uri(path: Path, mode: str = "ro") -> str:
    """Return a safe SQLite URI for a local path.

    Paths are percent-encoded so a filename containing ``?`` or ``#`` cannot
    change the URI parameters (which would otherwise select a different mode or
    database).
    """
    encoded = quote(str(Path(path).expanduser().resolve()), safe="/")
    return f"file:{encoded}?mode={mode}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stat_signature(st: os.stat_result) -> Dict[str, int]:
    return {
        "dev": int(st.st_dev),
        "ino": int(st.st_ino),
        "size": int(st.st_size),
        "mtime_ns": int(st.st_mtime_ns),
        "ctime_ns": int(st.st_ctime_ns),
        "nlink": int(st.st_nlink),
        "mode": int(st.st_mode),
    }


def _stat_signature_path(path: Path) -> Dict[str, int]:
    return _stat_signature(os.lstat(path))


def _check_expected_file(
    st: os.stat_result, expected_stat: Mapping[str, Any], *,
    expected_size: Optional[int] = None, label: str,
) -> None:
    if not stat_module.S_ISREG(st.st_mode):
        raise RestoreRefused(f"{label} is not a regular file")
    if int(st.st_nlink) != 1:
        raise RestoreRefused(f"{label} is a hardlink")
    current = _stat_signature(st)
    for key in ("dev", "ino", "size", "mtime_ns", "ctime_ns", "mode"):
        if key in expected_stat and int(expected_stat[key]) != current[key]:
            raise RestoreRefused(f"{label} changed or was replaced before copy")
    if expected_size is not None and int(st.st_size) != int(expected_size):
        raise RestoreRefused(f"{label} byte count changed before copy")


def _open_nofollow(path: Path, *, label: str) -> int:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(str(path), flags)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise RestoreRefused(f"{label} is a symlink") from exc
        raise
    try:
        st = os.fstat(fd)
        if not stat_module.S_ISREG(st.st_mode):
            raise RestoreRefused(f"{label} is not a regular file")
    except Exception:
        os.close(fd)
        raise
    return fd


def _open_relative_nofollow(root: Path, relative_name: str, *, label: str) -> int:
    """Open a manifest path by walking directory descriptors with NOFOLLOW.

    ``O_NOFOLLOW`` only protects the final path component.  Walking each
    component relative to an already-open directory descriptor prevents an
    intermediate directory from being replaced by a symlink between validation
    and use.
    """
    parts = PurePosixPath(relative_name).parts
    if not parts:
        raise RestoreRefused(f"{label} has an empty path")
    dir_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        dir_fd = os.open(str(root), dir_flags)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise RestoreRefused(f"{label} traverses a symlink") from exc
        raise RestoreRefused(f"{label} cannot be opened safely: {exc.strerror}") from exc
    try:
        for part in parts[:-1]:
            try:
                next_fd = os.open(part, dir_flags, dir_fd=dir_fd)
            except OSError as exc:
                if exc.errno == errno.ELOOP:
                    raise RestoreRefused(f"{label} traverses a symlink") from exc
                raise RestoreRefused(
                    f"{label} cannot be opened safely: {exc.strerror}") from exc
            os.close(dir_fd)
            dir_fd = next_fd
        try:
            fd = os.open(
                parts[-1],
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=dir_fd,
            )
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise RestoreRefused(f"{label} is a symlink") from exc
            raise RestoreRefused(f"{label} cannot be opened safely: {exc.strerror}") from exc
    finally:
        os.close(dir_fd)
    try:
        st = os.fstat(fd)
        if not stat_module.S_ISREG(st.st_mode):
            os.close(fd)
            raise RestoreRefused(f"{label} is not a regular file")
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
    return fd


def _hash_fd(fd: int) -> str:
    os.lseek(fd, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


def _sqlite_path_from_url(url: str) -> Optional[Path]:
    if not url or not url.startswith("sqlite"):
        return None
    path = url.partition(":///")[2]
    if not path or path == ":memory:":
        return None
    if "?" in path:
        path = path.split("?", 1)[0]
    candidate = Path(path)
    if not candidate.is_absolute():
        raise BackupConfigError(
            "DATABASE_URL SQLite path is relative; use an absolute path or "
            "unset DATABASE_URL so ATOM_DATA_DIR/atom.db is used")
    return candidate.resolve()


def _explicit_root(env: Mapping[str, str], name: str) -> Optional[Path]:
    raw = str(env.get(name) or "").strip()
    if not raw:
        return None
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        raise BackupConfigError(
            f"{name} must be an absolute path for a release-kit backup")
    if not candidate.exists():
        raise BackupConfigError(f"{name} is configured but missing: {candidate}")
    if not candidate.is_dir():
        raise BackupConfigError(f"{name} is configured but is not a directory: {candidate}")
    return candidate.resolve()


def _memory_root(env: Mapping[str, str], data_root: Path,
                 include_memory: bool) -> Tuple[Path, bool]:
    raw = str(env.get("LANCEDB_URI") or env.get("LANCEDB_URI_BASE") or "").strip()
    if not raw:
        return (data_root / "atom_memory").resolve(), True
    scheme = raw.split("://", 1)[0].lower() if "://" in raw else ""
    if scheme not in ALLOWED_MEMORY_SCHEMES:
        if include_memory:
            raise BackupConfigError(
                "LANCEDB_URI is not a local file path; --include-memory is "
                "unsupported for object-store memory")
        return Path(raw), False
    candidate = Path(raw.partition(":///")[2] if "://" in raw else raw).expanduser()
    if not candidate.is_absolute():
        raise BackupConfigError(
            "LANCEDB_URI must be absolute for a release-kit backup")
    return candidate.resolve(), True


def resolve_backup_sources(env: Mapping[str, str],
                           include_memory: bool) -> Dict[str, Any]:
    """Resolve the configured DB and managed store roots before backup.

    The release kit previously assumed ``ATOM_DATA_DIR/atom.db`` and
    ``ATOM_DATA_DIR/{office,sheet_datasets,email_attachments,atom_memory}``.
    That could silently omit an externally configured managed store or back up
    a different DB than the running app.  This resolver either returns the
    declared roots or refuses an ambiguous/unsupported configuration.
    """
    data_raw = str(env.get("ATOM_DATA_DIR") or "").strip()
    if not data_raw:
        raise BackupConfigError("ATOM_DATA_DIR is required for a release-kit backup")
    data_root = Path(data_raw).expanduser()
    if not data_root.is_absolute():
        raise BackupConfigError("ATOM_DATA_DIR must be absolute for a release-kit backup")
    data_root = data_root.resolve()
    if not data_root.is_dir():
        raise BackupConfigError(f"ATOM_DATA_DIR does not exist: {data_root}")

    db_from_url = _sqlite_path_from_url(str(env.get("DATABASE_URL") or ""))
    default_db = (data_root / DB_NAME).resolve()
    if db_from_url is not None and db_from_url != default_db:
        raise BackupConfigError(
            "DATABASE_URL and ATOM_DATA_DIR/atom.db disagree; refusing to "
            "back up an ambiguous database source")
    db_path = db_from_url or default_db
    if not db_path.is_file():
        raise BackupConfigError(f"database is missing: {db_path}")

    office = _explicit_root(env, "ATOM_OFFICE_DIR") or (data_root / "office")
    email = _explicit_root(env, "ATOM_EMAIL_ATTACHMENT_DIR") or (
        data_root / "email_attachments")
    sheet = (data_root / "sheet_datasets").resolve()
    memory, memory_local = _memory_root(env, data_root, include_memory)

    roots = {
        "database": {"source": str(db_path), "backup": DB_NAME, "included": True},
        "office": {"source": str(office.resolve()), "backup": "office",
                   "included": office.is_dir()},
        "sheet_datasets": {"source": str(sheet), "backup": "sheet_datasets",
                           "included": sheet.is_dir()},
        "email_attachments": {"source": str(email.resolve()), "backup": "email_attachments",
                              "included": email.is_dir()},
    }
    if include_memory:
        if not memory_local:
            raise BackupConfigError(
                "LANCEDB_URI is not a local file path; --include-memory is unsupported")
        if not memory.is_dir():
            raise BackupConfigError(
                f"memory store is missing but --include-memory was requested: {memory}")
        roots["atom_memory"] = {"source": str(memory.resolve()),
                                "backup": "atom_memory", "included": True}
    else:
        roots["atom_memory"] = {"source": str(memory), "backup": "atom_memory",
                                "included": False, "local": memory_local}
    return {"data_root": str(data_root), "database": str(db_path), "roots": roots}


def _reject_duplicate_keys(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise RestoreRefused(f"manifest contains duplicate key: {key!r}")
        out[key] = value
    return out


def _validate_row_counts(row_counts: Any) -> Dict[str, Optional[int]]:
    if not isinstance(row_counts, dict) or not row_counts:
        raise RestoreRefused("backup manifest has no non-empty row_counts map")
    out: Dict[str, Optional[int]] = {}
    for key, value in row_counts.items():
        if not isinstance(key, str) or not _ROW_COUNT_TABLE_RE.match(key):
            raise RestoreRefused(f"manifest row_counts key is not a safe table name: {key!r}")
        if isinstance(value, bool):
            raise RestoreRefused(f"manifest row_counts value is boolean, not a count: {key!r}")
        if value is not None:
            if not isinstance(value, int) or value < 0:
                raise RestoreRefused(
                    f"manifest row_counts value is not a non-negative integer: {key!r}")
        out[key] = value
    return out


def _load_manifest(backup_arg: Path) -> Tuple[Path, Path, Dict[str, Any], str]:
    source = backup_arg.expanduser()
    if source.is_dir():
        backup_dir = source.resolve()
        manifest_path = backup_dir / "BACKUP_MANIFEST.json"
    else:
        manifest_path = source.resolve()
        backup_dir = manifest_path.parent
    if not manifest_path.is_file():
        raise RestoreRefused(f"backup manifest is missing: {manifest_path}")
    if manifest_path.is_symlink():
        raise RestoreRefused("backup manifest is a symlink")
    fd = _open_nofollow(manifest_path, label="backup manifest")
    try:
        st = os.fstat(fd)
        if int(st.st_nlink) != 1:
            raise RestoreRefused("backup manifest is a hardlink")
        os.lseek(fd, 0, os.SEEK_SET)
        raw = b""
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            raw += chunk
        manifest_sha256 = hashlib.sha256(raw).hexdigest()
        try:
            manifest = json.loads(
                raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
        except RestoreRefused:
            raise
        except Exception as exc:  # noqa: BLE001
            raise RestoreRefused(
                f"backup manifest is unreadable: {type(exc).__name__}") from exc
    finally:
        os.close(fd)
    if not isinstance(manifest, dict):
        raise RestoreRefused("backup manifest must be a JSON object")
    if manifest.get("schema") != SCHEMA:
        raise RestoreRefused(
            f"unknown backup manifest schema: {manifest.get('schema')!r}")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise RestoreRefused("backup manifest has no files map")
    manifest["row_counts"] = _validate_row_counts(manifest.get("row_counts"))
    if not isinstance(manifest.get("source_data_dir"), str):
        raise RestoreRefused("backup manifest has no source_data_dir provenance")
    if manifest.get("sqlite_backup_api") is not True:
        raise RestoreRefused("backup manifest does not declare SQLite backup API use")
    if manifest.get("sqlite_integrity_check") is not True:
        raise RestoreRefused("backup manifest does not declare SQLite integrity")
    if not isinstance(manifest.get("memory_included"), bool):
        raise RestoreRefused("backup manifest has no boolean memory_included")
    return backup_dir, manifest_path, manifest, manifest_sha256


def _safe_relative_path(name: Any) -> str:
    if not isinstance(name, str) or not name:
        raise RestoreRefused("manifest file name is empty or not a string")
    if "\x00" in name or "\\" in name or name.startswith(("/", "~")):
        raise RestoreRefused(f"manifest path is not a safe relative path: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise RestoreRefused(f"manifest path escapes the backup: {name!r}")
    if path.parts[0] not in KNOWN_TOP_LEVEL:
        raise RestoreRefused(f"manifest path has an unknown top-level entry: {name!r}")
    normalized = posixpath.normpath(name)
    if normalized != name:
        raise RestoreRefused(f"manifest path is not normalized: {name!r}")
    return name


def _assert_no_db_sidecars(backup_dir: Path, manifest_files: Mapping[str, Any]) -> None:
    for suffix in ("-wal", "-shm", "-journal"):
        name = DB_NAME + suffix
        if name in manifest_files:
            raise RestoreRefused(
                "backup manifest lists a database sidecar; only a self-contained "
                f"checkpointed database is supported: {name}")
        if os.path.lexists(backup_dir / name):
            raise RestoreRefused(
                "backup contains a database sidecar; only a self-contained "
                f"checkpointed database is supported: {name}")


def _validate_manifest_files(
    backup_dir: Path, manifest: Dict[str, Any],
) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    files = manifest["files"]
    seen: Dict[str, str] = {}
    validated: Dict[str, Dict[str, Any]] = {}
    for raw_name, raw_meta in files.items():
        name = _safe_relative_path(raw_name)
        collision = unicodedata.normalize("NFC", name).casefold()
        if collision in seen:
            raise RestoreRefused(
                f"manifest paths collide after normalization: {seen[collision]!r} / {name!r}")
        seen[collision] = name
        if not isinstance(raw_meta, dict):
            raise RestoreRefused(f"manifest metadata is not an object: {name!r}")
        expected_sha = str(raw_meta.get("sha256") or "")
        expected_bytes = raw_meta.get("bytes")
        if len(expected_sha) != 64 or any(
                c not in "0123456789abcdef" for c in expected_sha.lower()):
            raise RestoreRefused(f"manifest sha256 is invalid: {name!r}")
        if isinstance(expected_bytes, bool) or not isinstance(expected_bytes, int) \
                or expected_bytes < 0:
            raise RestoreRefused(f"manifest byte count is invalid: {name!r}")
        candidate = backup_dir / name
        cursor = backup_dir
        for part in PurePosixPath(name).parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise RestoreRefused(f"manifest path traverses a symlink: {name!r}")
        if not candidate.is_file():
            raise RestoreRefused(f"manifest file is missing: {name!r}")
        fd = _open_relative_nofollow(
            backup_dir, name, label=f"manifest file {name!r}")
        try:
            st = os.fstat(fd)
            if stat_module.S_ISREG(st.st_mode) and int(st.st_nlink) != 1:
                raise RestoreRefused(f"manifest file is a hardlink: {name!r}")
            if int(st.st_size) != int(expected_bytes):
                raise RestoreRefused(f"manifest byte count mismatch: {name!r}")
            actual_sha = _hash_fd(fd)
        finally:
            os.close(fd)
        if actual_sha != expected_sha.lower():
            raise RestoreRefused(f"manifest sha256 mismatch: {name!r}")
        validated[name] = {
            "sha256": expected_sha.lower(),
            "bytes": int(expected_bytes),
            "stat": _stat_signature(st),
        }
    if DB_NAME not in validated:
        raise RestoreRefused("backup manifest does not include atom.db")
    _assert_no_db_sidecars(backup_dir, validated)
    memory_files = [name for name in validated if name.startswith("atom_memory/")]
    if manifest["memory_included"] and not memory_files:
        raise RestoreRefused("memory_included is true but atom_memory is empty")
    if not manifest["memory_included"] and memory_files:
        raise RestoreRefused("memory_included is false but atom_memory files are present")
    return validated, memory_files


def _verify_database(path: Path, row_counts: Mapping[str, Any]) -> Dict[str, Any]:
    """Verify integrity plus manifest row-count semantics.

    Semantics:
    * A non-negative integer means the table MUST exist and contain at least
      that many rows.  ``0`` is exact: a missing table is never silently read
      as zero.
    * ``None`` means the table did not exist in the backup source and MUST NOT
      exist now.
    * Keys must be simple SQL identifiers.  They are validated before quoting,
      so an untrusted manifest cannot inject SQL.
    """
    counts = _validate_row_counts(dict(row_counts))
    con = sqlite3.connect(sqlite_uri(path, "ro"), uri=True)
    try:
        row = con.execute("PRAGMA integrity_check").fetchone()
        if not row or row[0] != "ok":
            raise RestoreRefused("SQLite integrity_check failed")
        tables = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        got: Dict[str, Any] = {}
        for table, expected in counts.items():
            if not _ROW_COUNT_TABLE_RE.match(table):
                raise RestoreRefused(f"invalid row-count table name: {table!r}")
            if expected is None:
                if table in tables:
                    raise RestoreRefused(
                        f"row_counts declares {table} absent but it exists")
                got[table] = None
                continue
            if table not in tables:
                raise RestoreRefused(
                    f"row-count table is missing (never treated as zero): {table}")
            actual = con.execute(
                f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            got[table] = int(actual)
            if actual < expected:
                raise RestoreRefused(
                    f"SQLite row count for {table} is {actual}, expected at least {expected}")
            if expected == 0 and actual != 0:
                raise RestoreRefused(
                    f"SQLite row count for {table} is {actual}, expected exactly zero")
        return got
    finally:
        con.close()


def _live_roots(env: Mapping[str, str]) -> List[Path]:
    roots: List[Path] = []
    for key in ("ATOM_DATA_DIR", "ATOM_OFFICE_DIR", "ATOM_EMAIL_ATTACHMENT_DIR"):
        raw = str(env.get(key) or "").strip()
        if raw:
            try:
                roots.append(Path(raw).expanduser().resolve())
            except Exception:
                pass
    db = _sqlite_path_from_url(str(env.get("DATABASE_URL") or ""))
    if db is not None:
        roots.append(db.parent)
    raw_memory = str(env.get("LANCEDB_URI") or env.get("LANCEDB_URI_BASE") or "").strip()
    if raw_memory and "://" not in raw_memory:
        try:
            roots.append(Path(raw_memory).expanduser().resolve())
        except Exception:
            pass
    return roots


def _assert_no_symlink_components(path: Path, *, label: str) -> None:
    current = path
    while True:
        if current.is_symlink():
            raise RestoreRefused(f"{label} traverses a symlink: {current}")
        if current.parent == current:
            break
        current = current.parent


def _check_target(target: Path, source_data_dir: str, env: Mapping[str, str]) -> None:
    if os.path.lexists(target):
        raise RestoreRefused(
            "target already exists; restore requires an explicit non-existent target")
    try:
        source = Path(source_data_dir).expanduser().resolve()
        if target == source or source in target.parents or target in source.parents:
            raise RestoreRefused("target overlaps the backup source provenance path")
    except (OSError, ValueError):
        pass
    for live in _live_roots(env):
        if target == live or live in target.parents or target in live.parents:
            raise RestoreRefused("target overlaps a live configured data/store root")


def _safe_provenance_root(value: Any, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise RestoreRefused(f"manifest {field} is missing")
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        raise RestoreRefused(f"manifest {field} must be an absolute path")
    resolved = candidate.resolve()
    if resolved == Path("/"):
        raise RestoreRefused(f"manifest {field} must not be the filesystem root")
    return resolved


def _make_self_contained(db_path: Path) -> None:
    con = sqlite3.connect(str(db_path))
    try:
        try:
            con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error:
            pass
        con.execute("PRAGMA journal_mode=DELETE")
        con.commit()
    finally:
        con.close()
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = db_path.parent / (db_path.name + suffix)
        try:
            sidecar.unlink()
        except FileNotFoundError:
            pass


def _freeze_database(
    source_db: Path, binding: Mapping[str, Any], freeze_dir: Path,
) -> Path:
    expected_sha = str(binding["sha256"]).lower()
    expected_bytes = int(binding["bytes"])
    expected_stat = binding["stat"]
    _assert_no_db_sidecars(source_db.parent, {source_db.name: binding})
    src_fd = _open_relative_nofollow(
        source_db.parent, source_db.name, label="backup database")
    frozen = freeze_dir / "frozen-atom.db"
    dst_fd: Optional[int] = None
    try:
        before = os.fstat(src_fd)
        _check_expected_file(
            before, expected_stat, expected_size=expected_bytes,
            label="backup database")
        dst_fd = os.open(
            str(frozen),
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        digest = hashlib.sha256()
        total = 0
        hook_called = False
        while True:
            chunk = os.read(src_fd, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > expected_bytes:
                raise RestoreRefused("backup database grew while it was being frozen")
            digest.update(chunk)
            os.write(dst_fd, chunk)
            if not hook_called:
                hook_called = True
                hook = _READ_HOOK
                if hook is not None:
                    hook(source_db, total)
        os.fsync(dst_fd)
        after = os.fstat(src_fd)
        _check_expected_file(
            after, _stat_signature(before), expected_size=expected_bytes,
            label="backup database")
        if total != expected_bytes:
            raise RestoreRefused("backup database byte count changed while freezing")
        if digest.hexdigest() != expected_sha:
            raise RestoreRefused(
                "backup database differs from the validated manifest bytes")
    finally:
        if dst_fd is not None:
            os.close(dst_fd)
        os.close(src_fd)
    _assert_no_db_sidecars(source_db.parent, {source_db.name: binding})
    # Verify the frozen image itself from a nofollow descriptor before use.
    fd = _open_nofollow(frozen, label="frozen backup database")
    try:
        st = os.fstat(fd)
        if int(st.st_size) != expected_bytes or int(st.st_nlink) != 1:
            raise RestoreRefused("frozen backup database size/identity changed")
        if _hash_fd(fd) != expected_sha:
            raise RestoreRefused("frozen backup database hash changed")
    finally:
        os.close(fd)
    return frozen


def _copy_database(
    source_db: Path,
    stage_db: Path,
    row_counts: Mapping[str, Any],
    *,
    expected: Optional[Mapping[str, Any]] = None,
    freeze_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Copy from the exact manifest-validated DB bytes, never a later stat.

    The validated backup database is frozen through a nofollow descriptor into
    a private directory, re-hashed, and only then opened by the SQLite backup
    API.  A peer changing the backup path, inode, WAL/SHM sidecars, or file
    contents after validation cannot become the restored database.
    """
    binding = expected or _ACTIVE_DB_BINDING.get()
    if not isinstance(binding, Mapping):
        raise RestoreRefused(
            "database copy requires the validated manifest database binding")
    for key in ("sha256", "bytes", "stat"):
        if key not in binding:
            raise RestoreRefused("validated manifest database binding is incomplete")
    parent = Path(freeze_dir) if freeze_dir is not None else stage_db.parent
    freeze_root = Path(tempfile.mkdtemp(prefix=".restore-freeze-", dir=str(parent)))
    os.chmod(freeze_root, 0o700)
    try:
        frozen = _freeze_database(Path(source_db), binding, freeze_root)
        # Integrity/row counts on the frozen image (read-only; may create
        # sidecars in the private freeze directory, never in the backup).
        _verify_database(frozen, row_counts)
        # A read-only SQLite open must not have modified the frozen main file.
        if sha256_file(frozen) != str(binding["sha256"]).lower():
            raise RestoreRefused("frozen backup database changed while being opened")
        src = sqlite3.connect(sqlite_uri(frozen, "ro"), uri=True)
        dst = sqlite3.connect(str(stage_db))
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        _make_self_contained(stage_db)
        return _verify_database(stage_db, row_counts)
    finally:
        shutil.rmtree(freeze_root, ignore_errors=True)


def _copy_one_file(
    backup_dir: Path, name: str, destination: Path, meta: Mapping[str, Any],
) -> None:
    source = backup_dir / name
    src_fd = _open_relative_nofollow(
        backup_dir, name, label=f"backup file {name!r}")
    dst_fd: Optional[int] = None
    try:
        before = os.fstat(src_fd)
        _check_expected_file(
            before, meta["stat"], expected_size=int(meta["bytes"]),
            label=f"backup file {source.name!r}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        dst_fd = os.open(
            str(destination),
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        digest = hashlib.sha256()
        total = 0
        hook_called = False
        while True:
            chunk = os.read(src_fd, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            digest.update(chunk)
            os.write(dst_fd, chunk)
            if not hook_called:
                hook_called = True
                hook = _READ_HOOK
                if hook is not None:
                    hook(source, total)
        os.fsync(dst_fd)
        after = os.fstat(src_fd)
        _check_expected_file(
            after, _stat_signature(before), expected_size=int(meta["bytes"]),
            label=f"backup file {source.name!r}")
        if total != int(meta["bytes"]) or digest.hexdigest() != str(meta["sha256"]).lower():
            raise RestoreRefused(f"copied file changed or hash mismatch: {source.name!r}")
    except Exception:
        try:
            destination.unlink()
        except OSError:
            pass
        raise
    finally:
        if dst_fd is not None:
            os.close(dst_fd)
        os.close(src_fd)
    os.chmod(destination, 0o600 if _is_credential(name) else 0o644)
    # Re-read from a nofollow descriptor so the published staged bytes are the
    # same bytes the source descriptor produced.
    fd = _open_nofollow(destination, label=f"staged file {destination.name!r}")
    try:
        if int(os.fstat(fd).st_size) != int(meta["bytes"]) or _hash_fd(fd) != str(meta["sha256"]).lower():
            raise RestoreRefused(f"staged file hash mismatch: {source.name!r}")
    finally:
        os.close(fd)


def _is_credential(name: str) -> bool:
    top = PurePosixPath(name).parts[0]
    return top.startswith(CREDENTIAL_PREFIXES) or name.startswith("config/")


def _rebase_path(value: Any, mappings: Sequence[Tuple[Path, Path]]) -> Tuple[Any, bool]:
    if not isinstance(value, str) or not value:
        return value, False
    raw = Path(value)
    if not raw.is_absolute():
        return value, False
    try:
        resolved = raw.resolve()
    except OSError:
        return value, False
    for source, target in mappings:
        if resolved == source or source in resolved.parents:
            rel = resolved.relative_to(source)
            return str((target / rel).resolve()), True
    return value, False


def _mapping_list(source_data_dir: str, target_data: Path,
                  store_roots: Mapping[str, Any]) -> List[Tuple[Path, Path]]:
    mappings: List[Tuple[Path, Path]] = []
    source_data = _safe_provenance_root(source_data_dir, "source_data_dir")
    mappings.append((source_data, target_data))
    for name, default in (
        ("office", target_data / "office"),
        ("sheet_datasets", target_data / "sheet_datasets"),
        ("email_attachments", target_data / "email_attachments"),
        ("atom_memory", target_data / "atom_memory"),
    ):
        raw = None
        included = True
        if isinstance(store_roots, Mapping):
            entry = store_roots.get(name)
            if isinstance(entry, Mapping):
                raw = entry.get("source")
                included = bool(entry.get("included", True))
        # A memory store that was explicitly excluded may be an object-store
        # URI (s3://...); it has no local files to rebase and must not block a
        # truthful memory_included=false restore.
        if name == "atom_memory" and not included:
            continue
        if not raw:
            raw = str(source_data / name)
        candidate = Path(str(raw)).expanduser()
        if not candidate.is_absolute():
            if included:
                raise RestoreRefused(
                    f"manifest store_roots.{name}.source is not an absolute path")
            continue
        source = candidate.resolve()
        if source == Path("/"):
            raise RestoreRefused(
                f"manifest store_roots.{name}.source must not be the filesystem root")
        mappings.append((source, default))
    return mappings


def _parse_db_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        dt = value
    elif value:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            dt = None
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    dt = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    continue
            if dt is None:
                return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _next_created_at(previous: Any) -> str:
    now = datetime.now(timezone.utc)
    prev = _parse_db_datetime(previous)
    if prev is not None and prev >= now:
        now = prev + timedelta(microseconds=1)
    return now.strftime("%Y-%m-%d %H:%M:%S.%f")


def _json_object(text: Any) -> Optional[Dict[str, Any]]:
    if text is None:
        return None
    if isinstance(text, dict):
        return dict(text)
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _table_columns(con: sqlite3.Connection, table: str) -> List[str]:
    try:
        return [row[1] for row in con.execute(f'PRAGMA table_info("{table}")')]
    except sqlite3.Error:
        return []


def _content_row(
    con: sqlite3.Connection, canvas_id: str,
) -> Tuple[Optional[sqlite3.Row], Optional[Dict[str, Any]], Optional[str], Optional[sqlite3.Row]]:
    columns = set(_table_columns(con, "canvas_audit"))
    def col(name: str, default: str = "NULL") -> str:
        return f'"{name}"' if name in columns else f'{default} AS "{name}"'
    select = ", ".join((
        col("id"), col("details_json"), col("created_at"), col("action_type"),
        col("canvas_type"), col("tenant_id"),
    ))
    rows = con.execute(
        f"SELECT {select} FROM canvas_audit WHERE canvas_id=? "
        "ORDER BY created_at DESC, id DESC LIMIT 11",
        (canvas_id,),
    ).fetchall()
    if not rows:
        return None, None, None, None
    latest = rows[0]
    if str(latest["action_type"] or "") == "delete":
        return None, None, "deleted", latest
    for row in rows:
        details = _json_object(row["details_json"])
        if details is not None and ("content" in details or "data" in details):
            return row, details, None, latest
    return None, None, None, latest


def _rebase_office_payload(
    payload: Dict[str, Any], mapping: Tuple[Path, Path], *,
    office_scope: bool,
) -> Tuple[int, int]:
    changed = 0
    unresolved = 0
    source_office, target_office = mapping
    for key in ("office_file", "file_path"):
        if key not in payload:
            continue
        new, did = _rebase_path(payload.get(key), [(source_office, target_office)])
        if did:
            payload[key] = new
            changed += 1
        elif office_scope and str(payload.get(key) or "").startswith("/"):
            unresolved += 1
    return changed, unresolved


def _rewrite_managed_paths(
    db_path: Path, source_data_dir: str, target_data: Path,
    store_roots: Mapping[str, Any], manifest_sha256: str = "",
) -> Dict[str, Any]:
    """Rebase only current managed path projections, never history.

    Historical ``CanvasAudit`` rows are byte-for-byte immutable.  When the
    current content-bearing audit row carries a managed office binding, the
    restore appends a NEW restore-owned audit event with its own id, exact
    canvas/tenant scope, original-audit + manifest provenance, and the target
    binding.  ``read_canvas`` then serves the target binding without pretending
    the old operation was replayed unchanged.
    """
    mappings = _mapping_list(source_data_dir, target_data, store_roots)
    rewritten: Dict[str, int] = {}
    unresolved: Dict[str, int] = {}
    restore_events: List[Dict[str, Any]] = []

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        table_names = {row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        columns = _table_columns(con, "dataset_entries")
        if "parquet_path" in columns:
            count = 0
            for row in con.execute("SELECT rowid, parquet_path FROM dataset_entries"):
                new, changed = _rebase_path(row["parquet_path"], mappings)
                if changed:
                    con.execute("UPDATE dataset_entries SET parquet_path=? WHERE rowid=?",
                                (new, row["rowid"]))
                    count += 1
                elif str(row["parquet_path"] or "").startswith("/"):
                    unresolved["dataset_entries.parquet_path"] = unresolved.get(
                        "dataset_entries.parquet_path", 0) + 1
            rewritten["dataset_entries.parquet_path"] = count
        for table in ("ingested_documents", "accounting_documents"):
            columns = _table_columns(con, table)
            if "file_path" not in columns:
                continue
            count = 0
            for row in con.execute(f'SELECT rowid, file_path FROM "{table}"'):
                new, changed = _rebase_path(row["file_path"], mappings)
                if changed:
                    con.execute(f'UPDATE "{table}" SET file_path=? WHERE rowid=?',
                                (new, row["rowid"]))
                    count += 1
            rewritten[f"{table}.file_path"] = count

        if "goal_runs" in table_names:
            try:
                from prepare_production_data import rewrite_assignment_operational
            except Exception as exc:  # noqa: BLE001
                raise RestoreRefused(
                    "goal_runs exists but the kit's assignment path rewriter is "
                    f"unavailable: {type(exc).__name__}") from exc
            count = 0
            for row in con.execute("SELECT rowid, parameters FROM goal_runs"):
                data = _json_object(row["parameters"])
                if data is None:
                    continue
                assignment = ((data.get("task_lifecycle") or {}).get("assignment")
                              if isinstance(data, dict) else None)
                if not isinstance(assignment, dict):
                    continue
                changed = 0
                for source, target in mappings:
                    changed += rewrite_assignment_operational(
                        assignment, str(source), str(target))
                if changed:
                    data["task_lifecycle"]["assignment"] = assignment
                    con.execute("UPDATE goal_runs SET parameters=? WHERE rowid=?",
                                (json.dumps(data), row["rowid"]))
                    count += 1
            rewritten["goal_runs.parameters.assignment"] = count

        office_mapping = next((pair for pair in mappings
                               if pair[1] == target_data / "office"), None)
        canvas_count = 0
        event_count = 0
        deleted_skipped = 0
        if office_mapping is not None and "canvases" in table_names:
            canvas_columns = _table_columns(con, "canvases")
            select = ["id", "content"]
            for optional in ("canvas_type", "tenant_id"):
                if optional in canvas_columns:
                    select.append(optional)
            canvases = con.execute(
                f'SELECT {", ".join(select)} FROM canvases').fetchall()
            audit_columns = _table_columns(con, "canvas_audit")
            can_append_event = "canvas_audit" in table_names
            for canvas in canvases:
                canvas_id = str(canvas["id"])
                canvas_type = (canvas["canvas_type"]
                               if "canvas_type" in canvas.keys() else None)
                canvas_tenant = (canvas["tenant_id"]
                                 if "tenant_id" in canvas.keys() else None)
                canvas_payload = _json_object(canvas["content"]) or {}
                office_scope = bool(
                    "office_file" in canvas_payload
                    or str(canvas_type or "").startswith("office_"))
                if canvas_payload and ("office_file" in canvas_payload
                                       or "file_path" in canvas_payload):
                    changed, unresolved_count = _rebase_office_payload(
                        canvas_payload, office_mapping, office_scope=office_scope)
                    if unresolved_count:
                        unresolved["canvases.content.office_binding"] = (
                            unresolved.get("canvases.content.office_binding", 0)
                            + unresolved_count)
                    if changed:
                        con.execute("UPDATE canvases SET content=? WHERE id=?",
                                    (json.dumps(canvas_payload), canvas_id))
                        canvas_count += 1

                if not can_append_event:
                    continue
                row, details, state, latest_row = _content_row(con, canvas_id)
                if state == "deleted":
                    deleted_skipped += 1
                    continue
                if row is None or details is None:
                    continue
                payload_key = ("content" if isinstance(details.get("content"), dict)
                               else "data" if isinstance(details.get("data"), dict)
                               else None)
                if payload_key is None:
                    continue
                payload = dict(details[payload_key])
                content_office_scope = bool(
                    "office_file" in payload
                    or (office_scope and "file_path" in payload))
                changed, unresolved_count = _rebase_office_payload(
                    payload, office_mapping, office_scope=content_office_scope)
                if unresolved_count:
                    unresolved["canvas_audit.current_content.office_binding"] = (
                        unresolved.get("canvas_audit.current_content.office_binding", 0)
                        + unresolved_count)
                if not changed:
                    continue
                if not can_append_event:
                    raise RestoreRefused(
                        "a current canvas audit binding needs rebasing but "
                        "canvas_audit is unavailable")
                required = {"id", "canvas_id", "tenant_id", "action_type",
                            "details_json", "created_at"}
                missing = required.difference(audit_columns)
                if missing:
                    raise RestoreRefused(
                        "canvas_audit schema cannot accept a restore event: "
                        + ",".join(sorted(missing)))
                tenant = str(canvas_tenant or row["tenant_id"] or "")
                if not tenant:
                    raise RestoreRefused(
                        f"cannot append restore event for canvas {canvas_id}: "
                        "no authoritative tenant")
                new_details = dict(details)
                new_details[payload_key] = payload
                for key in ("operation_id", "evidence_refs", "postconditions",
                            "review_status"):
                    new_details.pop(key, None)
                new_details["restored_from"] = {
                    "audit_id": str(row["id"]),
                    "created_at": row["created_at"],
                    "action_type": row["action_type"],
                    "original_details_sha256": hashlib.sha256(
                        str(row["details_json"]).encode("utf-8")).hexdigest(),
                    "manifest_sha256": manifest_sha256,
                    "source_data_dir": source_data_dir,
                    "target_data_dir": str(target_data),
                    "binding": "rebased_to_target",
                    "note": (
                        "Restore-appended event. The original audit row, actor, "
                        "operation identity and material are unchanged; this "
                        "event certifies the current target binding only."
                    ),
                }
                new_id = str(uuid.uuid4())
                created_at = _next_created_at(
                    latest_row["created_at"] if latest_row is not None
                    else row["created_at"])
                values: Dict[str, Any] = {
                    "id": new_id,
                    "canvas_id": canvas_id,
                    "tenant_id": tenant,
                    "session_id": None,
                    "action_type": _RESTORE_ACTION,
                    "user_id": None,
                    "agent_id": None,
                    "episode_id": None,
                    "canvas_type": (row["canvas_type"] or canvas_type or "generic"),
                    "details_json": json.dumps(new_details),
                    "created_at": created_at,
                }
                insert_columns = [name for name in values if name in audit_columns]
                placeholders = ", ".join("?" for _ in insert_columns)
                quoted = ", ".join(f'"{name}"' for name in insert_columns)
                con.execute(
                    f"INSERT INTO canvas_audit ({quoted}) VALUES ({placeholders})",
                    [values[name] for name in insert_columns],
                )
                event_count += 1
                restore_events.append({
                    "canvas_id": canvas_id,
                    "audit_id": new_id,
                    "action_type": _RESTORE_ACTION,
                    "created_at": created_at,
                    "original_audit_id": str(row["id"]),
                    "manifest_sha256": manifest_sha256,
                })
        rewritten["canvases.content.office_binding"] = canvas_count
        rewritten["canvas_audit.restore_events_appended"] = event_count
        rewritten["canvas_audit.restore_events_skipped_deleted"] = deleted_skipped
        con.commit()
    finally:
        con.close()
    return {
        "rewritten": rewritten,
        "unresolved": unresolved,
        "restore_events": restore_events,
        "mappings": [
            {"source": str(source), "target": str(target)}
            for source, target in mappings
        ],
    }


def _rename_noreplace(old: Path, new: Path) -> bool:
    """Best-effort atomic no-replace directory rename.

    Returns True when the platform performed the operation.  Raises
    ``RestoreRefused`` if the target already exists.  Returns False only when
    the platform/filesystem does not support the flag (caller falls back).
    """
    libc = ctypes.CDLL(None, use_errno=True)
    old_b = os.fsencode(str(old))
    new_b = os.fsencode(str(new))
    if sys.platform == "darwin" and hasattr(libc, "renamex_np"):
        fn = libc.renamex_np
        fn.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        fn.restype = ctypes.c_int
        res = fn(old_b, new_b, 0x00000004)  # RENAME_EXCL
    elif sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        fn = libc.renameat2
        fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                       ctypes.c_char_p, ctypes.c_uint]
        fn.restype = ctypes.c_int
        at_fdcwd = -100
        res = fn(at_fdcwd, old_b, at_fdcwd, new_b, 0x1)  # RENAME_NOREPLACE
    else:
        return False
    if res == 0:
        return True
    err = ctypes.get_errno()
    if err in (errno.EEXIST, errno.ENOTEMPTY):
        raise RestoreRefused("target was created concurrently")
    if err in (errno.ENOSYS, errno.ENOTSUP, errno.EINVAL):
        return False
    raise OSError(err, os.strerror(err), str(new))


def _publish_no_replace(stage: Path, target: Path) -> None:
    if os.path.lexists(target):
        raise RestoreRefused("target was created concurrently")
    hook = _PUBLISH_HOOK
    if hook is not None:
        hook(target)
    if _rename_noreplace(stage, target):
        return
    # Portable fallback: atomically create the target directory first, then
    # move each child.  Never rename over a peer path.
    try:
        os.mkdir(target, 0o700)
    except FileExistsError as exc:
        raise RestoreRefused("target was created concurrently") from exc
    placeholder = os.lstat(target)
    try:
        for child in sorted(stage.iterdir()):
            current = os.lstat(target)
            if (current.st_dev, current.st_ino) != (
                    placeholder.st_dev, placeholder.st_ino):
                raise RestoreRefused("target was replaced concurrently")
            os.replace(child, target / child.name)
        stage.rmdir()
    except Exception:
        # The target is ours and may be partially populated.  Do not delete a
        # peer path if it was replaced; leave the partial target for the
        # committed_unverified report.
        current = os.lstat(target)
        if (current.st_dev, current.st_ino) == (
                placeholder.st_dev, placeholder.st_ino):
            shutil.rmtree(target, ignore_errors=True)
        raise


def _create_claim(parent: Path, target: Path) -> Tuple[Path, int, Dict[str, int], str]:
    claim = parent / f".{target.name}.restore.claim"
    flags = (os.O_CREAT | os.O_EXCL | os.O_WRONLY
             | getattr(os, "O_NOFOLLOW", 0))
    try:
        fd = os.open(str(claim), flags, 0o600)
    except FileExistsError as exc:
        raise RestoreRefused("another restore/claim already owns this target") from exc
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise RestoreRefused("target claim path is a symlink") from exc
        raise
    try:
        token = str(uuid.uuid4())
        payload = json.dumps({
            "token": token, "pid": os.getpid(), "target": str(target),
        }).encode("utf-8")
        os.write(fd, payload)
        os.fsync(fd)
        st = os.fstat(fd)
    except Exception:
        os.close(fd)
        try:
            claim.unlink()
        except OSError:
            pass
        raise
    return claim, fd, _stat_signature(st), token


def _release_claim(claim: Path, fd: Optional[int],
                   signature: Optional[Mapping[str, int]],
                   token: Optional[str]) -> None:
    if fd is None:
        return
    try:
        try:
            current = os.lstat(claim)
        except FileNotFoundError:
            current = None
        held = os.fstat(fd)
        owns = (current is not None
                and signature is not None
                and token is not None
                and (int(current.st_dev), int(current.st_ino))
                == (int(held.st_dev), int(held.st_ino))
                == (int(signature["dev"]), int(signature["ino"])))
        if owns:
            # The path may still be our inode but have been overwritten in
            # place by a peer.  Only remove a claim whose exact token is ours.
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                raw = os.read(fd, 1024 * 1024)
                parsed = json.loads(raw.decode("utf-8"))
                owns = isinstance(parsed, dict) and parsed.get("token") == token
            except (OSError, ValueError):
                owns = False
        if owns:
            try:
                os.unlink(claim)
            except FileNotFoundError:
                pass
    finally:
        os.close(fd)


def restore_backup(
    *,
    backup_arg: str,
    target_arg: str,
    env: Mapping[str, str],
) -> Dict[str, Any]:
    """Verify and restore one manifest-bound local backup into a fresh root."""
    backup_dir, manifest_path, manifest, manifest_sha256 = _load_manifest(
        Path(backup_arg))
    files, _memory_files = _validate_manifest_files(backup_dir, manifest)
    source_data_dir = _safe_provenance_root(
        manifest.get("source_data_dir"), "source_data_dir")
    raw_target = Path(target_arg).expanduser()
    if not raw_target.is_absolute():
        raise RestoreRefused("target-data-dir must be an absolute path")
    _assert_no_symlink_components(raw_target, label="target path")
    target = raw_target.resolve()
    _check_target(target, str(source_data_dir), env)
    parent = target.parent
    if not parent.is_dir():
        raise RestoreRefused("target parent directory does not exist")
    if parent.is_symlink():
        raise RestoreRefused("target parent is a symlink")

    claim: Optional[Path] = None
    claim_fd: Optional[int] = None
    claim_signature: Optional[Dict[str, int]] = None
    claim_token: Optional[str] = None
    stage: Optional[Path] = None
    published = False
    binding_token = None
    try:
        claim, claim_fd, claim_signature, claim_token = _create_claim(parent, target)
        binding = {
            "sha256": files[DB_NAME]["sha256"],
            "bytes": files[DB_NAME]["bytes"],
            "stat": files[DB_NAME]["stat"],
            "manifest_sha256": manifest_sha256,
        }
        binding_token = _ACTIVE_DB_BINDING.set(binding)
        stage = Path(tempfile.mkdtemp(
            prefix=f".{target.name}.restore-", dir=str(parent)))
        os.chmod(stage, 0o700)
        stage_db = stage / DB_NAME
        row_counts = _copy_database(
            backup_dir / DB_NAME, stage_db, manifest["row_counts"],
            expected=binding, freeze_dir=stage)
        copied = 0
        for name, meta in files.items():
            if name == DB_NAME or name in DB_SIDECARS:
                # The DB is produced from the frozen validated image by the
                # SQLite backup API; source WAL/SHM files are never published.
                continue
            source = backup_dir / name
            destination = stage / name
            _copy_one_file(backup_dir, name, destination, meta)
            copied += 1
        for name, meta in files.items():
            if name == DB_NAME or name in DB_SIDECARS:
                continue
            destination = stage / name
            if destination.stat().st_size != meta["bytes"]:
                raise RestoreRefused("staged file byte count mismatch")
            if sha256_file(destination) != meta["sha256"]:
                raise RestoreRefused("staged file sha256 mismatch")
        portability = _rewrite_managed_paths(
            stage_db, str(source_data_dir), target,
            manifest.get("store_roots") if isinstance(manifest.get("store_roots"), dict) else {},
            manifest_sha256=manifest_sha256,
        )
        if portability.get("unresolved"):
            raise RestoreRefused(
                "managed path portability is unresolved; refusing to publish "
                "a partially rebased world: "
                + json.dumps(portability["unresolved"], sort_keys=True))
        _make_self_contained(stage_db)
        for suffix in ("-wal", "-shm", "-journal"):
            if os.path.lexists(stage_db.parent / (stage_db.name + suffix)):
                raise RestoreRefused(
                    f"staged database has an ambiguous sidecar: atom.db{suffix}")
        row_counts = _verify_database(stage_db, manifest["row_counts"])
        staged_db_sha256 = sha256_file(stage_db)

        _publish_no_replace(stage, target)
        published = True
        stage = None

        # Post-publish readback. A failure here is committed_unverified, not a
        # safe refusal and not a reason to repeat blindly.
        try:
            if os.path.islink(target):
                raise RestoreUncertain("published target is a symlink")
            for suffix in ("-wal", "-shm", "-journal"):
                if os.path.lexists(target / (DB_NAME + suffix)):
                    raise RestoreUncertain(
                        f"published database has an ambiguous sidecar: atom.db{suffix}")
            row_counts = _verify_database(target / DB_NAME, manifest["row_counts"])
            for name, meta in files.items():
                if name == DB_NAME or name in DB_SIDECARS:
                    continue
                destination = target / name
                fd = _open_nofollow(destination, label=f"published file {name!r}")
                try:
                    if int(os.fstat(fd).st_size) != meta["bytes"]:
                        raise RestoreUncertain("published file byte count mismatch")
                    if _hash_fd(fd) != meta["sha256"]:
                        raise RestoreUncertain("published file sha256 mismatch")
                finally:
                    os.close(fd)
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False, "status": "committed_unverified", "error": str(exc),
                "backup": str(backup_dir), "manifest": str(manifest_path),
                "manifest_sha256": manifest_sha256,
                "target": str(target), "source_data_dir": str(source_data_dir),
                "row_counts": row_counts, "files_verified": copied,
                "memory_included": bool(manifest.get("memory_included")),
                "memory_restored": bool(manifest.get("memory_included")),
                "memory_files_verified": (
                    len(_memory_files) if manifest.get("memory_included") else 0),
                "portability": portability,
                "staged_db_sha256": staged_db_sha256,
                "manifest_db_sha256": files[DB_NAME]["sha256"],
            }
        return {
            "ok": True, "status": "verified",
            "backup": str(backup_dir), "manifest": str(manifest_path),
            "manifest_sha256": manifest_sha256,
            "target": str(target), "source_data_dir": str(source_data_dir),
            "row_counts": row_counts, "files_verified": copied,
            "memory_included": bool(manifest.get("memory_included")),
            "memory_restored": bool(manifest.get("memory_included")),
            "memory_files_verified": (
                len(_memory_files) if manifest.get("memory_included") else 0),
            "portability": portability,
            "staged_db_sha256": staged_db_sha256,
            "manifest_db_sha256": files[DB_NAME]["sha256"],
        }
    except RestoreRefused:
        if stage is not None:
            shutil.rmtree(stage, ignore_errors=True)
        raise
    except Exception as exc:  # noqa: BLE001
        if stage is not None:
            shutil.rmtree(stage, ignore_errors=True)
        if published:
            return {
                "ok": False, "status": "committed_unverified",
                "error": f"{type(exc).__name__}: {exc}",
                "backup": str(backup_dir), "manifest": str(manifest_path),
                "manifest_sha256": manifest_sha256,
                "target": str(target), "source_data_dir": str(source_data_dir),
                "row_counts": {}, "files_verified": 0,
                "memory_included": bool(manifest.get("memory_included")),
                "memory_restored": bool(manifest.get("memory_included")),
                "portability": {},
            }
        raise RestoreRefused(f"{type(exc).__name__}: {exc}") from exc
    finally:
        if binding_token is not None:
            _ACTIVE_DB_BINDING.reset(binding_token)
        if claim is not None:
            _release_claim(claim, claim_fd, claim_signature, claim_token)
