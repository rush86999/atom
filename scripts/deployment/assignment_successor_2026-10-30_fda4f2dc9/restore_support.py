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
- Staging + ``os.replace`` and explicit copy/symlink checks follow Python's
  documented ``shutil``/``os`` semantics:
  https://docs.python.org/3.14/library/shutil.html
  https://docs.python.org/3/library/os.html
"""
from __future__ import annotations

import hashlib
import json
import os
import posixpath
import shutil
import sqlite3
import tempfile
import unicodedata
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

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


class BackupConfigError(RuntimeError):
    """The configured backup source roots are ambiguous or unsupported."""


class RestoreRefused(RuntimeError):
    """The restore refused before publishing anything to the target."""


class RestoreUncertain(RuntimeError):
    """The target was published but could not be independently re-verified."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stat_signature(path: Path) -> Tuple[int, int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, stat.st_ino


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


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


def _memory_root(env: Mapping[str, str], data_root: Path, include_memory: bool) -> Tuple[Path, bool]:
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


def resolve_backup_sources(env: Mapping[str, str], include_memory: bool) -> Dict[str, Any]:
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


def _load_manifest(backup_arg: Path) -> Tuple[Path, Path, Dict[str, Any]]:
    source = backup_arg.expanduser()
    if source.is_dir():
        backup_dir = source.resolve()
        manifest_path = backup_dir / "BACKUP_MANIFEST.json"
    else:
        manifest_path = source.resolve()
        backup_dir = manifest_path.parent
    if not manifest_path.is_file():
        raise RestoreRefused(f"backup manifest is missing: {manifest_path}")
    try:
        manifest = json.loads(
            manifest_path.read_text(),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except RestoreRefused:
        raise
    except Exception as exc:  # noqa: BLE001
        raise RestoreRefused(f"backup manifest is unreadable: {type(exc).__name__}") from exc
    if not isinstance(manifest, dict):
        raise RestoreRefused("backup manifest must be a JSON object")
    if manifest.get("schema") != SCHEMA:
        raise RestoreRefused(
            f"unknown backup manifest schema: {manifest.get('schema')!r}")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise RestoreRefused("backup manifest has no files map")
    if not isinstance(manifest.get("row_counts"), dict):
        raise RestoreRefused("backup manifest has no row_counts map")
    if not isinstance(manifest.get("source_data_dir"), str):
        raise RestoreRefused("backup manifest has no source_data_dir provenance")
    if manifest.get("sqlite_backup_api") is not True:
        raise RestoreRefused("backup manifest does not declare SQLite backup API use")
    if manifest.get("sqlite_integrity_check") is not True:
        raise RestoreRefused("backup manifest does not declare SQLite integrity")
    if not isinstance(manifest.get("memory_included"), bool):
        raise RestoreRefused("backup manifest has no boolean memory_included")
    return backup_dir, manifest_path, manifest


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
        if len(expected_sha) != 64 or any(c not in "0123456789abcdef" for c in expected_sha.lower()):
            raise RestoreRefused(f"manifest sha256 is invalid: {name!r}")
        if not isinstance(expected_bytes, int) or expected_bytes < 0:
            raise RestoreRefused(f"manifest byte count is invalid: {name!r}")
        candidate = backup_dir / name
        try:
            candidate.resolve().relative_to(backup_dir.resolve())
        except ValueError as exc:
            raise RestoreRefused(f"manifest path escapes the backup: {name!r}") from exc
        cursor = backup_dir
        for part in PurePosixPath(name).parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise RestoreRefused(f"manifest path traverses a symlink: {name!r}")
        if not candidate.is_file():
            raise RestoreRefused(f"manifest file is missing: {name!r}")
        stat = candidate.stat()
        if stat.st_nlink > 1:
            raise RestoreRefused(f"manifest file is a hardlink: {name!r}")
        if stat.st_size != expected_bytes:
            raise RestoreRefused(f"manifest byte count mismatch: {name!r}")
        if sha256_file(candidate) != expected_sha.lower():
            raise RestoreRefused(f"manifest sha256 mismatch: {name!r}")
        validated[name] = {
            "sha256": expected_sha.lower(),
            "bytes": expected_bytes,
            "stat": _stat_signature(candidate),
        }
    if DB_NAME not in validated:
        raise RestoreRefused("backup manifest does not include atom.db")
    memory_files = [name for name in validated if name.startswith("atom_memory/")]
    if manifest["memory_included"] and not memory_files:
        raise RestoreRefused("memory_included is true but atom_memory is empty")
    if not manifest["memory_included"] and memory_files:
        raise RestoreRefused("memory_included is false but atom_memory files are present")
    return validated, memory_files


def _verify_database(path: Path, row_counts: Mapping[str, Any]) -> Dict[str, int]:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        row = con.execute("PRAGMA integrity_check").fetchone()
        if not row or row[0] != "ok":
            raise RestoreRefused("SQLite integrity_check failed")
        got: Dict[str, int] = {}
        for table, expected in row_counts.items():
            if expected is None:
                continue
            try:
                got[table] = con.execute(
                    f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            except sqlite3.Error:
                got[table] = 0
            if got[table] < int(expected):
                raise RestoreRefused(
                    f"SQLite row count for {table} is {got[table]}, expected at least {expected}")
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


def _check_target(target: Path, source_data_dir: str, env: Mapping[str, str]) -> None:
    if target.is_symlink():
        raise RestoreRefused("target path is a symlink")
    if target.exists() and not target.is_dir():
        raise RestoreRefused("target exists and is not a directory")
    if target.exists() and any(target.iterdir()):
        raise RestoreRefused("target exists and is not empty")
    if target.exists() and (target / DB_NAME).exists():
        raise RestoreRefused("target already contains atom.db")
    try:
        source = Path(source_data_dir).expanduser().resolve()
        if target == source or source in target.parents or target in source.parents:
            raise RestoreRefused("target overlaps the backup source provenance path")
    except (OSError, ValueError):
        pass
    for live in _live_roots(env):
        if target == live or live in target.parents or target in live.parents:
            raise RestoreRefused("target overlaps a live configured data/store root")


def _copy_database(source_db: Path, stage_db: Path, row_counts: Mapping[str, Any]) -> Dict[str, int]:
    before = _stat_signature(source_db)
    src = sqlite3.connect(f"file:{source_db}?mode=ro", uri=True)
    dst = sqlite3.connect(stage_db)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    after = _stat_signature(source_db)
    if before != after:
        raise RestoreRefused("backup database changed while it was being restored")
    return _verify_database(stage_db, row_counts)


def _copy_one_file(source: Path, destination: Path, meta: Mapping[str, Any]) -> None:
    before = _stat_signature(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    after = _stat_signature(source)
    if before != after:
        raise RestoreRefused("backup file changed while it was being restored")
    if destination.stat().st_size != meta["bytes"]:
        raise RestoreRefused("copied file byte count mismatch")
    if sha256_file(destination) != meta["sha256"]:
        raise RestoreRefused("copied file sha256 mismatch")


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


def _mapping_list(source_data_dir: str, target_data: Path, store_roots: Mapping[str, Any]) -> List[Tuple[Path, Path]]:
    mappings: List[Tuple[Path, Path]] = []
    try:
        source_data = Path(source_data_dir).expanduser().resolve()
    except (OSError, ValueError):
        source_data = None
    if source_data is not None:
        mappings.append((source_data, target_data))
    for name, default in (
        ("office", target_data / "office"),
        ("sheet_datasets", target_data / "sheet_datasets"),
        ("email_attachments", target_data / "email_attachments"),
        ("atom_memory", target_data / "atom_memory"),
    ):
        raw = (store_roots.get(name) or {}).get("source") if isinstance(store_roots, Mapping) else None
        if not raw and source_data is not None:
            raw = str(source_data / name)
        if raw:
            try:
                source = Path(raw).expanduser().resolve()
                mappings.append((source, default))
            except (OSError, ValueError):
                continue
    return mappings


def _rewrite_managed_paths(
    db_path: Path, source_data_dir: str, target_data: Path,
    store_roots: Mapping[str, Any],
) -> Dict[str, Any]:
    """Rewrite only current managed path columns/bindings, not history.

    This follows the existing ``prepare_production_data.py`` known-path rule:
    dataset parquet paths, optional document file paths, and assignment
    operational paths are rewritten.  In addition, the current Canvas.content
    office binding and the latest content-bearing CanvasAudit office binding
    are rebased so ``read_canvas`` does not keep borrowing the old source root.
    Historical audit rows, receipts, provenance and operation bindings are not
    rewritten.
    """
    mappings = _mapping_list(source_data_dir, target_data, store_roots)
    rewritten: Dict[str, int] = {}
    unresolved: Dict[str, int] = {}

    def _table_columns(con: sqlite3.Connection, table: str) -> List[str]:
        try:
            return [row[1] for row in con.execute(f'PRAGMA table_info("{table}")')]
        except sqlite3.Error:
            return []

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
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

        if "goal_runs" in {row[0] for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}:
            try:
                from prepare_production_data import rewrite_assignment_operational
            except Exception:
                rewrite_assignment_operational = None
            if rewrite_assignment_operational is not None:
                count = 0
                for row in con.execute("SELECT rowid, parameters FROM goal_runs"):
                    try:
                        data = json.loads(row["parameters"] or "{}")
                    except (TypeError, ValueError):
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

        # Current Canvas.content office bindings (and only the latest
        # content-bearing audit row, which read_canvas treats as current state).
        table_names = {row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        office_mapping = next((pair for pair in mappings
                               if pair[1] == target_data / "office"), None)
        canvas_count = 0
        audit_count = 0
        if office_mapping is not None and "canvases" in table_names:
            source_office, target_office = office_mapping
            canvases = con.execute(
                "SELECT id, content, canvas_type FROM canvases").fetchall()
            for canvas in canvases:
                try:
                    content = json.loads(canvas["content"] or "{}")
                except (TypeError, ValueError):
                    continue
                if not isinstance(content, dict):
                    continue
                if ("office_file" not in content
                        and not str(canvas["canvas_type"] or "").startswith("office_")):
                    continue
                changed = False
                for key in ("office_file", "file_path"):
                    new, did = _rebase_path(content.get(key), [(source_office, target_office)])
                    if did:
                        content[key] = new
                        changed = True
                    elif str(content.get(key) or "").startswith("/"):
                        unresolved[f"canvases.content.{key}"] = unresolved.get(
                            f"canvases.content.{key}", 0) + 1
                if changed:
                    con.execute("UPDATE canvases SET content=? WHERE id=?",
                                (json.dumps(content), canvas["id"]))
                    canvas_count += 1
                if "canvas_audit" not in table_names:
                    continue
                latest = con.execute(
                    "SELECT id, details_json FROM canvas_audit "
                    "WHERE canvas_id=? AND details_json IS NOT NULL "
                    "ORDER BY created_at DESC, id DESC LIMIT 20",
                    (canvas["id"],)).fetchall()
                for row in latest:
                    try:
                        details = json.loads(row["details_json"] or "{}")
                    except (TypeError, ValueError):
                        continue
                    payload = details.get("content")
                    if not isinstance(payload, dict):
                        payload = details.get("data")
                    if not isinstance(payload, dict) or "office_file" not in payload:
                        continue
                    audit_changed = False
                    for key in ("office_file", "file_path"):
                        new, did = _rebase_path(payload.get(key), [(source_office, target_office)])
                        if did:
                            payload[key] = new
                            audit_changed = True
                        elif str(payload.get(key) or "").startswith("/"):
                            unresolved[f"canvas_audit.latest_content.{key}"] = unresolved.get(
                                f"canvas_audit.latest_content.{key}", 0) + 1
                    if audit_changed:
                        if "content" in details and isinstance(details.get("content"), dict):
                            details["content"] = payload
                        elif "data" in details and isinstance(details.get("data"), dict):
                            details["data"] = payload
                        con.execute("UPDATE canvas_audit SET details_json=? WHERE id=?",
                                    (json.dumps(details), row["id"]))
                        audit_count += 1
                    break
        rewritten["canvases.content.office_binding"] = canvas_count
        rewritten["canvas_audit.latest_content.office_binding"] = audit_count
        con.commit()
    finally:
        con.close()
    return {"rewritten": rewritten, "unresolved": unresolved, "mappings": [
        {"source": str(source), "target": str(target)} for source, target in mappings
    ]}


def restore_backup(
    *,
    backup_arg: str,
    target_arg: str,
    env: Mapping[str, str],
) -> Dict[str, Any]:
    """Verify and restore one manifest-bound local backup into a fresh root."""
    backup_dir, manifest_path, manifest = _load_manifest(Path(backup_arg))
    files, _memory_files = _validate_manifest_files(backup_dir, manifest)
    source_data_dir = str(manifest.get("source_data_dir") or "")
    raw_target = Path(target_arg).expanduser()
    if not raw_target.is_absolute():
        raise RestoreRefused("target-data-dir must be an absolute path")
    if raw_target.is_symlink():
        raise RestoreRefused("target path is a symlink")
    target = raw_target.resolve()
    _check_target(target, source_data_dir, env)
    parent = target.parent
    if not parent.is_dir():
        raise RestoreRefused("target parent directory does not exist")
    if parent.is_symlink():
        raise RestoreRefused("target parent is a symlink")

    claim = parent / f".{target.name}.restore.claim"
    try:
        fd = os.open(str(claim), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
    except FileExistsError as exc:
        raise RestoreRefused("another restore/claim already owns this target") from exc

    stage: Optional[Path] = None
    published = False
    try:
        stage = Path(tempfile.mkdtemp(
            prefix=f".{target.name}.restore-", dir=str(parent)))
        os.chmod(stage, 0o700)
        stage_db = stage / DB_NAME
        row_counts = _copy_database(
            backup_dir / DB_NAME, stage_db, manifest["row_counts"])
        copied = 0
        for name, meta in files.items():
            if name == DB_NAME or name in DB_SIDECARS:
                # The DB is produced by the SQLite backup API and verified by
                # integrity/row counts; its bytes need not equal the source
                # backup file (and are intentionally changed by path rewrite).
                # Source WAL/SHM files are never published independently.
                continue
            source = backup_dir / name
            destination = stage / name
            _copy_one_file(source, destination, meta)
            if _is_credential(name):
                os.chmod(destination, 0o600)
            copied += 1
        _verify_database(stage_db, manifest["row_counts"])
        for name, meta in files.items():
            if name == DB_NAME or name in DB_SIDECARS:
                continue
            destination = stage / name
            if destination.stat().st_size != meta["bytes"]:
                raise RestoreRefused("staged file byte count mismatch")
            if sha256_file(destination) != meta["sha256"]:
                raise RestoreRefused("staged file sha256 mismatch")
        portability = _rewrite_managed_paths(
            stage_db, source_data_dir, target,
            manifest.get("store_roots") if isinstance(manifest.get("store_roots"), dict) else {},
        )
        if portability.get("unresolved"):
            raise RestoreRefused(
                "managed path portability is unresolved; refusing to publish "
                "a partially rebased world: "
                + json.dumps(portability["unresolved"], sort_keys=True))
        _verify_database(stage_db, manifest["row_counts"])

        if target.exists():
            if target.is_symlink() or any(target.iterdir()):
                raise RestoreRefused("target was created concurrently")
            target.rmdir()
        if target.exists():
            raise RestoreRefused("target was created concurrently")
        os.replace(stage, target)
        published = True
        stage = None

        # Post-publish readback. A failure here is committed_unverified, not a
        # safe refusal and not a reason to repeat blindly.
        try:
            _verify_database(target / DB_NAME, manifest["row_counts"])
            for name, meta in files.items():
                if name == DB_NAME or name in DB_SIDECARS:
                    continue
                destination = target / name
                if destination.stat().st_size != meta["bytes"]:
                    raise RestoreUncertain("published file byte count mismatch")
                if sha256_file(destination) != meta["sha256"]:
                    raise RestoreUncertain("published file sha256 mismatch")
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False, "status": "committed_unverified", "error": str(exc),
                "backup": str(backup_dir), "manifest": str(manifest_path),
                "manifest_sha256": sha256_file(manifest_path),
                "target": str(target), "source_data_dir": source_data_dir,
                "row_counts": row_counts, "files_verified": copied,
                "memory_included": bool(manifest.get("memory_included")),
                "memory_restored": bool(manifest.get("memory_included")),
                "portability": portability,
            }
        return {
            "ok": True, "status": "verified",
            "backup": str(backup_dir), "manifest": str(manifest_path),
            "manifest_sha256": sha256_file(manifest_path),
            "target": str(target), "source_data_dir": source_data_dir,
            "row_counts": row_counts, "files_verified": copied,
            "memory_included": bool(manifest.get("memory_included")),
            "memory_restored": bool(manifest.get("memory_included")),
            "portability": portability,
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
                "manifest_sha256": sha256_file(manifest_path),
                "target": str(target), "source_data_dir": source_data_dir,
                "row_counts": {}, "files_verified": 0,
                "memory_included": bool(manifest.get("memory_included")),
                "memory_restored": bool(manifest.get("memory_included")),
                "portability": {},
            }
        raise RestoreRefused(f"{type(exc).__name__}: {exc}") from exc
    finally:
        try:
            claim.unlink(missing_ok=True)
        except OSError:
            pass
