#!/usr/bin/env python3
"""Real-PostgreSQL acceptance for the 20261117 document-lineage upgrade.

What this proves
----------------
The repository already tests the ``dataset_entries.source_document_id``
migration against scratch SQLite files and compiles its PostgreSQL DDL
statically (``backend/tests/test_document_lineage_upgrade.py``). SQLite-only
evidence cannot show that the real Alembic revision upgrades a real existing
PostgreSQL table, because PostgreSQL objects (nullable ``VARCHAR``, named
constraint/index metadata, transaction behaviour) differ from SQLite.

This harness owns one brand-new, private PostgreSQL cluster and runs the
migration's own ``upgrade()``/``downgrade()`` through a real Alembic
``Operations`` context against a legacy-shaped ``dataset_entries`` table. It
then proves:

* the legacy table's rows, indexes and ``uq_dataset_entries_version`` survive;
* the nullable lineage column and its non-unique index are added and valid;
* the version unique constraint is still enforced;
* new lineage values and new rows are writable;
* re-running the upgrade is a no-op and repairs a missing index;
* downgrade removes only the lineage upgrade, and re-upgrade restores it;
* a database without ``dataset_entries`` stays a safe no-op;
* only this cluster's PostgreSQL process is restarted (clean fast stop/start,
  not crash recovery) and the new connection still sees the sentinel rows,
  lineage values and unique constraint;
* cleanup stops only the process whose data directory and marker identity
  match this scratch root.

Safety contract (enforced before mkdir or initdb)
-------------------------------------------------
* the scratch root must be an absolute, non-symlink, empty-or-absent path
  strictly under ``/private/tmp`` (override only for isolated tests through
  the ``allowed_root`` argument);
* protected directories (``/``, ``/Users``, the repo, ``backend/data`` …),
  relative paths, parent symlinks and non-empty roots are refused;
* ``initdb`` runs with a unique role, ``--auth-local=trust`` and
  ``--auth-host=reject``; the generated config sets ``listen_addresses = ''``
  and a private 0700 Unix socket directory, so no TCP port (5432/5433/8181/
  8082 included) is opened or contacted;
* a marker file records the cluster id, data directory, socket directory,
  port and role; start/restart/stop require the marker, ``postmaster.pid``
  and ``ps`` command line (``-D <our data directory>``) to agree, and use
  ``pg_ctl -D <our data directory>`` only — no process-name or raw-PID kill;
* ``TESTING=1``, an absolute scratch-only ``DATABASE_URL``,
  ``PYTHON_DOTENV_DISABLED=1`` and a synthetic ``SECRET_KEY`` are set before
  any optional backend import; the harness itself opens only the explicit
  SQLAlchemy PostgreSQL engine built from the marker's Unix socket. No
  backend module (and therefore no ``core.database`` engine) is imported.

Scope limits
------------
This is one PostgreSQL 14.24 (Homebrew) local-cluster acceptance, not a
PostgreSQL 16, all-version or full-application qualification. It never
connects to an existing cluster, Docker, the repository's e2e localhost:5433
database, an owner DSN or any provider API. It does not delete the scratch
cluster: evidence and data are preserved for inspection.

Usage
-----
::

    python scripts/acceptance/postgres_document_lineage_upgrade.py
    python scripts/acceptance/postgres_document_lineage_upgrade.py \
        --scratch-root /private/tmp/atom-pg-lineage-20261117-<unique>

The default root is a fresh unique directory under ``/private/tmp``; the
report is written to ``<scratch-root>/report.json`` and printed on stdout.
Exit codes: 0 passed, 1 failed after a cluster was prepared, 2 safety refusal
(nothing created).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import random
import re
import shlex
import shutil
import stat
import subprocess
import sys
import time
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import sqlalchemy as sa
from sqlalchemy.engine import URL
from sqlalchemy.pool import NullPool

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
MIGRATION_FILE = (
    BACKEND_DIR / "alembic/versions/20261117_dataset_entry_source_document.py"
)

PRE_REVISION = "20261116_action_autonomy_rules"
MIGRATION_REVISION = "20261117_dataset_entry_lineage"
TABLE = "dataset_entries"
COLUMN = "source_document_id"
INDEX = "ix_dataset_entries_source_document_id"
FILE_LOOKUP_INDEX = "ix_dataset_entries_file_lookup"

OLD_COLUMNS = (
    "id",
    "workspace_id",
    "tenant_id",
    "created_by",
    "source_kind",
    "source",
    "external_id",
    "file_name",
    "content_hash",
    "entity_name",
    "dataset_name",
    "parquet_path",
    "row_count",
    "column_count",
    "columns_json",
    "source_modified_at",
    "ingested_at",
    "status",
    "superseded_by",
)

LEGACY_INDEXES = {
    "ix_dataset_entries_workspace_id": ("workspace_id",),
    "ix_dataset_entries_tenant_id": ("tenant_id",),
    "ix_dataset_entries_created_by": ("created_by",),
    "ix_dataset_entries_external_id": ("external_id",),
    "ix_dataset_entries_dataset_name": ("dataset_name",),
    FILE_LOOKUP_INDEX: ("source", "external_id", "status"),
}

SEED_ROWS = (
    {
        "id": "seed-active",
        "workspace_id": "ws-acceptance",
        "tenant_id": "tenant-acceptance",
        "created_by": "user-acceptance",
        "source_kind": "file",
        "source": "upload",
        "external_id": "sha1-of-source-bytes",
        "file_name": "budget.csv",
        "content_hash": "hash-active",
        "entity_name": "Sheet1",
        "dataset_name": "budget_sheet1",
        "parquet_path": "/scratch/acceptance/budget.parquet",
        "row_count": 3,
        "column_count": 2,
        "columns_json": '["item", "amount"]',
        "source_modified_at": "2026-11-01T10:00:00+00:00",
        "ingested_at": "2026-11-01T10:00:01+00:00",
        "status": "active",
        "superseded_by": None,
    },
    {
        "id": "seed-superseded",
        "workspace_id": "ws-acceptance",
        "tenant_id": "tenant-acceptance",
        "created_by": "user-acceptance",
        "source_kind": "file",
        "source": "upload",
        "external_id": "sha1-of-older-bytes",
        "file_name": "budget.csv",
        "content_hash": "hash-superseded",
        "entity_name": "Sheet1",
        "dataset_name": "budget_sheet1",
        "parquet_path": "/scratch/acceptance/older-budget.parquet",
        "row_count": 2,
        "column_count": 2,
        "columns_json": '["item", "amount"]',
        "source_modified_at": "2026-10-01T10:00:00+00:00",
        "ingested_at": "2026-10-01T10:00:01+00:00",
        "status": "superseded",
        "superseded_by": "seed-active",
    },
    {
        "id": "seed-removed",
        "workspace_id": None,
        "tenant_id": None,
        "created_by": None,
        "source_kind": "file",
        "source": "google_drive",
        "external_id": "drive-file-removed",
        "file_name": 'résumé "Q3".csv',
        "content_hash": "hash-removed",
        "entity_name": "Q3",
        "dataset_name": "resume_q3",
        "parquet_path": "/scratch/acceptance/removed.parquet",
        "row_count": 0,
        "column_count": 1,
        "columns_json": '["note"]',
        "source_modified_at": None,
        "ingested_at": "2026-09-01T08:00:00+00:00",
        "status": "removed",
        "superseded_by": None,
    },
    {
        "id": "seed-other-source",
        "workspace_id": "ws-acceptance",
        "tenant_id": "tenant-acceptance",
        "created_by": "user-acceptance",
        "source_kind": "file",
        "source": "zoho_workdrive",
        "external_id": "zoho-file-1",
        "file_name": "invoices.xlsx",
        "content_hash": "hash-invoices",
        "entity_name": "invoices",
        "dataset_name": "invoices_entity",
        "parquet_path": "/scratch/acceptance/invoices.parquet",
        "row_count": 12,
        "column_count": 4,
        "columns_json": '["id", "vendor", "amount", "due"]',
        "source_modified_at": "2026-11-10T12:30:00+00:00",
        "ingested_at": "2026-11-10T12:30:05+00:00",
        "status": "active",
        "superseded_by": None,
    },
)

SEED_IDS = tuple(row["id"] for row in SEED_ROWS)
NEW_LINEAGE_ROW_ID = "seed-lineage-new"

SHARED_PORTS = frozenset({5432, 5433, 8181, 8082})
DEFAULT_ALLOWED_ROOT = Path("/private/tmp")
DEFAULT_PG_BINDIR = Path("/usr/local/bin")
MARKER_NAME = ".atom-pg-lineage-acceptance.json"
MARKER_FORMAT = "atom-postgres-document-lineage-acceptance/1"
REPORT_FORMAT = "atom-postgres-document-lineage-acceptance-report/1"
SOCKET_DIR_NAME = "sock"
#: macOS ``sockaddr_un.sun_path`` is 104 bytes including the terminator.
MAX_SOCKET_PATH_BYTES = 100

PROTECTED_ROOTS = (
    Path("/"),
    Path("/usr"),
    Path("/etc"),
    Path("/var"),
    Path("/bin"),
    Path("/sbin"),
    Path("/System"),
    Path("/Library"),
    Path("/Applications"),
    Path("/Users"),
    Path("/private/var"),
    Path("/private/etc"),
)


class SafetyRefusal(RuntimeError):
    """Refused before creating anything (bad/preexisting/unsafe scratch)."""


class AcceptanceFailure(RuntimeError):
    """The cluster was prepared but a contract check failed."""


# ---------------------------------------------------------------------------
# Pure safety / cluster helpers (unit-tested without a database)
# ---------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolved(path: Path | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _has_symlink_component(path: Path) -> bool:
    """True when any existing component of ``path`` is a symlink.

    ``Path.resolve`` happily follows a symlinked parent (macOS ``/tmp`` is the
    canonical example). A scratch cluster must be reachable through real
    directories only, so compare the lexical absolute path with the resolved
    path; they differ exactly when a component is a symlink.
    """
    absolute = Path(os.path.abspath(os.path.expanduser(str(path))))
    return _resolved(absolute) != absolute


def validate_scratch_root(
    raw: str | os.PathLike[str],
    *,
    allowed_root: Path | str = DEFAULT_ALLOWED_ROOT,
    repo_root: Path | str = REPO_ROOT,
    protected_paths: Iterable[Path | str] = (),
) -> Path:
    """Validate a scratch root without creating or modifying anything.

    Raises ``SafetyRefusal`` for relative paths, symlinked parents, protected
    locations, the allowed root itself, a non-directory, a non-empty directory,
    or a socket path that would exceed the Unix-socket limit.
    """
    text = str(raw or "").strip()
    if not text:
        raise SafetyRefusal("scratch root is required")
    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        raise SafetyRefusal(f"scratch root must be absolute: {text}")
    if _has_symlink_component(candidate):
        raise SafetyRefusal(
            f"scratch root or a parent is a symlink: {candidate}")

    root = _resolved(candidate)
    allowed = _resolved(allowed_root)
    if root == allowed or not _is_within(root, allowed):
        raise SafetyRefusal(
            f"scratch root must be a child of {allowed}: {root}")

    protected = {_resolved(path) for path in PROTECTED_ROOTS}
    protected.add(_resolved(repo_root))
    protected.add(_resolved(Path(repo_root) / "backend" / "data"))
    protected.update(_resolved(path) for path in protected_paths)
    for blocked in protected:
        if root == blocked or (blocked != Path("/") and _is_within(root, blocked)):
            raise SafetyRefusal(
                f"scratch root overlaps protected path {blocked}: {root}")

    if root.exists():
        if root.is_symlink():
            raise SafetyRefusal(f"scratch root is a symlink: {root}")
        if not root.is_dir():
            raise SafetyRefusal(f"scratch root is not a directory: {root}")
        try:
            owner = root.stat().st_uid
        except OSError as exc:
            raise SafetyRefusal(f"cannot stat scratch root {root}: {exc}") from exc
        if owner != os.getuid():
            raise SafetyRefusal(
                f"scratch root is owned by uid {owner}, not this user: {root}")
        try:
            entries = list(os.scandir(root))
        except OSError as exc:
            raise SafetyRefusal(
                f"cannot inspect scratch root {root}: {exc}") from exc
        if entries:
            raise SafetyRefusal(
                f"scratch root must be empty, found {len(entries)} "
                f"entr{'y' if len(entries) == 1 else 'ies'}: {root}")

    socket_path = root / SOCKET_DIR_NAME / ".s.PGSQL.00000"
    if len(str(socket_path).encode()) > MAX_SOCKET_PATH_BYTES:
        raise SafetyRefusal(
            f"scratch root is too long for a Unix socket path "
            f"({len(str(socket_path).encode())} > {MAX_SOCKET_PATH_BYTES}): "
            f"{root}")
    return root


def create_scratch_layout(
    raw: str | os.PathLike[str],
    *,
    allowed_root: Path | str = DEFAULT_ALLOWED_ROOT,
    repo_root: Path | str = REPO_ROOT,
    protected_paths: Iterable[Path | str] = (),
) -> Path:
    """Validate, then create the private root/socket/home/tmp directories."""
    root = validate_scratch_root(
        raw,
        allowed_root=allowed_root,
        repo_root=repo_root,
        protected_paths=protected_paths,
    )
    try:
        root.mkdir(mode=0o700)
    except FileExistsError:
        # validate_scratch_root already proved it is an empty real directory.
        pass
    except OSError as exc:
        raise SafetyRefusal(f"cannot create scratch root {root}: {exc}") from exc
    for path in (root, root / SOCKET_DIR_NAME, root / "home", root / "tmp"):
        path.mkdir(mode=0o700, exist_ok=True)
        try:
            os.chmod(path, 0o700)
        except OSError as exc:
            raise SafetyRefusal(f"cannot make {path} private 0700: {exc}") from exc
        if stat.S_IMODE(path.stat().st_mode) != 0o700:
            raise SafetyRefusal(f"{path} is not mode 0700")
    return root


def marker_path(root: Path) -> Path:
    return root / MARKER_NAME


def write_marker(root: Path, marker: Mapping[str, Any]) -> None:
    """Atomically write the ownership marker as a 0600 regular file."""
    path = marker_path(root)
    if path.is_symlink():
        raise SafetyRefusal(f"marker path is a symlink: {path}")
    payload = json.dumps(dict(marker), indent=2, sort_keys=True) + "\n"
    temporary = root / f".{MARKER_NAME}.{os.getpid()}.tmp"
    descriptor = os.open(
        temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def load_marker(root: Path) -> dict[str, Any]:
    """Load and structurally verify this cluster's ownership marker."""
    path = marker_path(root)
    if path.is_symlink():
        raise SafetyRefusal(f"marker path is a symlink: {path}")
    if not path.is_file():
        raise SafetyRefusal(f"ownership marker is missing: {path}")
    try:
        marker = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SafetyRefusal(f"cannot read marker {path}: {exc}") from exc
    verify_marker(marker, root)
    return marker


def verify_marker(marker: Mapping[str, Any], root: Path | str) -> None:
    """Reject markers that do not describe exactly this owned cluster."""
    scratch = _resolved(Path(root))
    if not isinstance(marker, Mapping):
        raise SafetyRefusal("marker is not a JSON object")
    if marker.get("format") != MARKER_FORMAT:
        raise SafetyRefusal("marker format does not match this harness")
    if marker.get("owned") is not True:
        raise SafetyRefusal("marker does not assert ownership")
    if not isinstance(marker.get("cluster_id"), str) or not marker["cluster_id"]:
        raise SafetyRefusal("marker cluster_id is missing")
    if _resolved(marker.get("scratch_root", "")) != scratch:
        raise SafetyRefusal("marker scratch_root does not match")
    data = _resolved(marker.get("data_directory", ""))
    sockets = _resolved(marker.get("socket_directory", ""))
    if data != scratch / "data" or not _is_within(data, scratch):
        raise SafetyRefusal("marker data_directory is not this root's data/")
    if sockets != scratch / SOCKET_DIR_NAME or not _is_within(
            sockets, scratch):
        raise SafetyRefusal("marker socket_directory is not this root's sock/")
    if not isinstance(marker.get("port"), int):
        raise SafetyRefusal("marker port is not an integer")
    if marker["port"] in SHARED_PORTS:
        raise SafetyRefusal(f"marker port is a shared port: {marker['port']}")
    for key in ("username", "database"):
        value = marker.get(key)
        if not isinstance(value, str) or not value:
            raise SafetyRefusal(f"marker {key} is missing")
    if not re.fullmatch(r"[a-z0-9_]+", marker["database"]):
        raise SafetyRefusal("marker database name is not a safe identifier")


def choose_port(
    *,
    rng: random.Random | None = None,
    forbidden: Iterable[int] = SHARED_PORTS,
    socket_dir: Path | None = None,
) -> int:
    """Pick a random private port that cannot be a shared/owner port."""
    chooser = rng or random.SystemRandom()
    blocked = {int(port) for port in forbidden}
    for _ in range(200):
        port = chooser.randint(20000, 60000)
        if port in blocked:
            continue
        if socket_dir is not None and (
                socket_dir / f".s.PGSQL.{port}").exists():
            continue
        return port
    raise SafetyRefusal("could not choose a private PostgreSQL port")


def assert_safe_port(port: int, *, expected: int | None = None) -> None:
    if not isinstance(port, int) or not (1 <= port <= 65535):
        raise SafetyRefusal(f"invalid PostgreSQL port: {port!r}")
    if port in SHARED_PORTS:
        raise SafetyRefusal(f"refusing shared PostgreSQL port {port}")
    if expected is not None and port != expected:
        raise SafetyRefusal(f"port {port} is not this cluster's port {expected}")


def build_database_url(marker: Mapping[str, Any], database: str | None = None
                       ) -> URL:
    """Explicit psycopg2 URL over this cluster's Unix socket directory only."""
    verify_marker(marker, marker["scratch_root"])
    assert_safe_port(marker["port"], expected=marker["port"])
    return URL.create(
        "postgresql+psycopg2",
        username=marker["username"],
        database=database or marker["database"],
        query={
            "host": marker["socket_directory"],
            "port": str(marker["port"]),
            "application_name": "atom-document-lineage-acceptance",
        },
    )


def assert_socket_only_url(
    url: URL | str, marker: Mapping[str, Any]
) -> dict[str, Any]:
    """Reject any URL that is not exactly this marker's Unix socket target."""
    parsed = url if isinstance(url, URL) else sa.engine.make_url(str(url))
    if not str(parsed.drivername).startswith("postgresql+psycopg2"):
        raise SafetyRefusal(f"unexpected PostgreSQL driver: {parsed.drivername}")
    host = parsed.query.get("host")
    port_text = parsed.query.get("port")
    if not isinstance(host, str) or not host:
        raise SafetyRefusal("PostgreSQL URL has no explicit socket host")
    if not Path(host).is_absolute():
        raise SafetyRefusal(f"PostgreSQL host is not an absolute socket: {host}")
    if host.lower() in {"localhost", "127.0.0.1", "::1"}:
        raise SafetyRefusal(f"refusing TCP loopback PostgreSQL host: {host}")
    if _resolved(host) != _resolved(marker["socket_directory"]):
        raise SafetyRefusal(f"PostgreSQL socket host is not owned: {host}")
    try:
        port = int(port_text)
    except (TypeError, ValueError) as exc:
        raise SafetyRefusal("PostgreSQL URL has no explicit integer port") from exc
    assert_safe_port(port, expected=marker["port"])
    if parsed.host is not None or parsed.port is not None:
        raise SafetyRefusal("PostgreSQL URL must not use a TCP host/port form")
    return {
        "drivername": str(parsed.drivername),
        "socket_directory": host,
        "port": port,
        "database": parsed.database,
        "username": parsed.username,
    }


def render_cluster_config(socket_dir: Path, port: int) -> str:
    """Settings appended to the owned cluster's postgresql.conf."""
    assert_safe_port(port)
    if not Path(socket_dir).is_absolute():
        raise SafetyRefusal("socket directory must be absolute")
    escaped = str(socket_dir).replace("'", "''")
    return (
        "\n# --- atom document-lineage acceptance (owned scratch cluster) ---\n"
        "# No TCP listener at all: connections are Unix sockets in a 0700 dir.\n"
        "listen_addresses = ''\n"
        f"unix_socket_directories = '{escaped}'\n"
        "unix_socket_permissions = 0700\n"
        f"port = {port}\n"
        "bonjour = off\n"
        "ssl = off\n"
        "max_connections = 20\n"
        "shared_buffers = 16MB\n"
        "timezone = 'UTC'\n"
        "log_timezone = 'UTC'\n"
        "logging_collector = off\n"
    )


def build_initdb_argv(
    bindir: Path | str, data_dir: Path | str, username: str,
) -> list[str]:
    if not re.fullmatch(r"[a-z0-9_]{1,63}", username):
        raise SafetyRefusal(f"unsafe PostgreSQL role name: {username}")
    return [
        str(Path(bindir) / "initdb"),
        "-D", str(data_dir),
        "-U", username,
        "--auth-local=trust",
        "--auth-host=reject",
        "--no-locale",
        "--encoding=UTF8",
    ]


def build_pg_ctl_argv(
    bindir: Path | str, data_dir: Path | str, *arguments: str,
) -> list[str]:
    return [str(Path(bindir) / "pg_ctl"), "-D", str(data_dir), *arguments]


def read_postmaster_pid(data_dir: Path) -> int | None:
    path = Path(data_dir) / "postmaster.pid"
    try:
        first = path.read_text(encoding="utf-8").splitlines()[0].strip()
    except (OSError, IndexError, UnicodeDecodeError):
        return None
    try:
        pid = int(first)
    except ValueError:
        return None
    return pid if pid > 1 else None


def read_process_command(pid: int) -> str | None:
    try:
        proc = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    command = proc.stdout.strip()
    return command or None


def process_matches_cluster(
    command: str | None, data_dir: Path | str,
) -> bool:
    """Exact ``postgres -D <our data directory>`` command check.

    Paths are compared after ``resolve`` so ``data-other`` or
    ``data/../data-other`` can never satisfy ``data``; no substring matching.
    """
    if not command:
        return False
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    expected = _resolved(data_dir)
    for index, token in enumerate(tokens):
        candidate: str | None = None
        if token == "-D":
            if index + 1 < len(tokens):
                candidate = tokens[index + 1]
        elif token.startswith("-D") and len(token) > 2:
            candidate = token[2:]
        if candidate and _resolved(candidate) == expected:
            return True
    return False


def parse_pg_ctl_pid(output: str | None) -> int | None:
    if not output:
        return None
    match = re.search(r"server is running \(PID:\s*(\d+)\)", output)
    if match:
        return int(match.group(1))
    match = re.search(r"PID:\s*(\d+)", output)
    return int(match.group(1)) if match else None


def assert_cluster_identity(
    marker: Mapping[str, Any],
    *,
    expected_pid: int | None = None,
    pidfile_pid: int | None = None,
    process_command: str | None = None,
    status_output: str | None = None,
) -> int:
    """Refuse to treat a process as ours unless marker/pidfile/ps agree.

    Injection points exist so the refusal paths can be unit-tested without a
    PostgreSQL server. A mismatch always raises; callers must never fall back
    to a name/PID kill.
    """
    verify_marker(marker, marker["scratch_root"])
    data_dir = Path(marker["data_directory"])
    pid = pidfile_pid if pidfile_pid is not None else read_postmaster_pid(data_dir)
    if pid is None:
        raise SafetyRefusal(f"no postmaster.pid under {data_dir}")
    if expected_pid is not None and pid != expected_pid:
        raise SafetyRefusal(
            f"postmaster.pid {pid} != expected owned PID {expected_pid}")
    if pid <= 1 or pid == os.getpid():
        raise SafetyRefusal(f"refusing implausible postmaster PID {pid}")

    command = (
        process_command if process_command is not None
        else read_process_command(pid)
    )
    if not process_matches_cluster(command, data_dir):
        raise SafetyRefusal(
            f"PID {pid} is not this cluster's postgres -D {data_dir}: "
            f"{command!r}")

    if status_output is None:
        status_output = pg_ctl_status(Path(marker["pg_bindir"]), data_dir)
    status_pid = parse_pg_ctl_pid(status_output)
    if status_pid is None:
        raise SafetyRefusal(
            f"pg_ctl status did not report a running PID: {status_output!r}")
    if status_pid != pid:
        raise SafetyRefusal(
            f"pg_ctl status PID {status_pid} != postmaster.pid {pid}")
    return pid


def pg_ctl_status(bindir: Path, data_dir: Path) -> str:
    proc = subprocess.run(
        build_pg_ctl_argv(bindir, data_dir, "status"),
        capture_output=True, text=True, timeout=20, check=False,
    )
    if proc.returncode != 0:
        raise SafetyRefusal(
            f"pg_ctl status failed ({proc.returncode}): "
            f"{(proc.stderr or proc.stdout).strip()}")
    return (proc.stdout or "") + (proc.stderr or "")


def socket_file_path(marker: Mapping[str, Any]) -> Path:
    return (
        Path(marker["socket_directory"])
        / f".s.PGSQL.{marker['port']}"
    )


def assert_private_socket(marker: Mapping[str, Any]) -> dict[str, Any]:
    socket_path = socket_file_path(marker)
    try:
        info = socket_path.lstat()
    except OSError as exc:
        raise AcceptanceFailure(f"Unix socket is missing: {socket_path}") from exc
    if not stat.S_ISSOCK(info.st_mode):
        raise AcceptanceFailure(f"not a Unix socket: {socket_path}")
    directory_mode = stat.S_IMODE(
        Path(marker["socket_directory"]).stat().st_mode)
    if directory_mode != 0o700:
        raise AcceptanceFailure(
            f"socket directory mode is {oct(directory_mode)}, expected 0700")
    file_mode = stat.S_IMODE(info.st_mode)
    if file_mode & 0o077:
        raise AcceptanceFailure(
            f"socket file mode {oct(file_mode)} exposes group/other access")
    return {
        "socket_file": str(socket_path),
        "socket_directory_mode": oct(directory_mode),
        "socket_file_mode": oct(file_mode),
    }


def tcp_listen_ports(pid: int) -> list[int] | None:
    """TCP LISTEN ports for our postmaster, or None when lsof is absent."""
    executable = shutil.which("lsof")
    if not executable:
        return None
    proc = subprocess.run(
        [executable, "-nP", "-a", "-p", str(pid), "-iTCP", "-sTCP:LISTEN"],
        capture_output=True, text=True, timeout=15, check=False,
    )
    if proc.returncode not in (0, 1):
        raise AcceptanceFailure(
            f"lsof failed ({proc.returncode}): {proc.stderr.strip()}")
    ports: set[int] = set()
    for line in proc.stdout.splitlines()[1:]:
        match = re.search(r":(\d+)\s*(?:\(LISTEN\))?\s*$", line)
        if match:
            ports.add(int(match.group(1)))
    return sorted(ports)


def canonical_digest(payload: Any) -> str:
    text = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=_json_default)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def _canonical_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: _json_default(value) for key, value in dict(row).items()}
        for row in rows
    ]


def sanitized_environment(
    root: Path, bindir: Path, database_url: str,
) -> dict[str, str]:
    """A minimal child environment: no DSN, PG* or owner/home variables."""
    return {
        "PATH": f"{bindir}:/usr/bin:/bin",
        "HOME": str(root / "home"),
        "TMPDIR": str(root / "tmp"),
        "LANG": "C",
        "LC_ALL": "C",
        "LC_CTYPE": "C",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "TESTING": "1",
        "DATABASE_URL": database_url,
        "PYTHON_DOTENV_DISABLED": "1",
        "SECRET_KEY": "atom-postgres-lineage-acceptance-synthetic",
        "PGCONNECT_TIMEOUT": "5",
        "PGCLIENTENCODING": "UTF8",
    }


# ---------------------------------------------------------------------------
# Alembic/migration loading (backend/alembic must not shadow the runtime)
# ---------------------------------------------------------------------------
def _backend_path_entry(entry: str) -> bool:
    if not entry:
        return False
    try:
        return _resolved(entry) == _resolved(BACKEND_DIR)
    except OSError:
        return False


def load_alembic_runtime():
    """Import installed Alembic even when ``backend/`` is on ``sys.path``."""
    shadowed = [
        name for name, module in list(sys.modules.items())
        if (name == "alembic" or name.startswith("alembic."))
        and getattr(module, "__file__", None)
        and _is_within(_resolved(module.__file__), BACKEND_DIR / "alembic")
    ]
    for name in shadowed:
        sys.modules.pop(name, None)
    saved = list(sys.path)
    sys.path = [
        entry for entry in sys.path
        if not _backend_path_entry(entry) and Path(entry or ".").name != "backend"
    ]
    try:
        import alembic
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
    finally:
        sys.path = saved
    module_file = getattr(alembic, "__file__", None)
    if not module_file or _is_within(_resolved(module_file), BACKEND_DIR):
        raise AcceptanceFailure(
            f"backend/alembic shadowed the Alembic runtime: {module_file}")
    return MigrationContext, Operations


def load_migration():
    load_alembic_runtime()
    spec = importlib.util.spec_from_file_location(
        "atom_dataset_entry_lineage_migration", MIGRATION_FILE)
    if spec is None or spec.loader is None:
        raise AcceptanceFailure(f"cannot load migration {MIGRATION_FILE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# SQL contracts
# ---------------------------------------------------------------------------
LEGACY_CREATE_SQL = f"""
CREATE TABLE {TABLE} (
    id VARCHAR NOT NULL PRIMARY KEY,
    workspace_id VARCHAR,
    tenant_id VARCHAR,
    created_by VARCHAR,
    source_kind VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    external_id VARCHAR NOT NULL,
    file_name VARCHAR,
    content_hash VARCHAR NOT NULL,
    entity_name VARCHAR NOT NULL,
    dataset_name VARCHAR NOT NULL,
    parquet_path VARCHAR NOT NULL,
    row_count INTEGER,
    column_count INTEGER,
    columns_json JSON,
    source_modified_at TIMESTAMP WITH TIME ZONE,
    ingested_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR NOT NULL,
    superseded_by VARCHAR,
    CONSTRAINT uq_dataset_entries_version UNIQUE
        (source_kind, source, external_id, content_hash, entity_name)
)
"""

INSERT_ROW_SQL = sa.text(
    "INSERT INTO dataset_entries ("
    + ", ".join(OLD_COLUMNS)
    + ") VALUES ("
    + ", ".join(
        f"CAST(:{name} AS JSON)" if name == "columns_json"
        else (
            f"CAST(:{name} AS TIMESTAMP WITH TIME ZONE)"
            if name in {"source_modified_at", "ingested_at"} else f":{name}"
        )
        for name in OLD_COLUMNS
    )
    + ")"
)


def _index_columns(index: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        index.get("column_names")
        or [column.get("name") for column in index.get("expressions", [])]
        or ()
    )


class AcceptanceHarness:
    def __init__(
        self,
        scratch_root: str | None,
        *,
        pg_bindir: str | Path = DEFAULT_PG_BINDIR,
        allowed_root: Path | str = DEFAULT_ALLOWED_ROOT,
        repo_root: Path | str = REPO_ROOT,
    ) -> None:
        self.scratch_root_argument = scratch_root
        self.pg_bindir = _resolved(pg_bindir)
        self.allowed_root = Path(allowed_root)
        self.repo_root = Path(repo_root)
        self.root: Path | None = None
        self.marker: dict[str, Any] | None = None
        self.env: dict[str, str] = {}
        self.engine: sa.Engine | None = None
        self.migration = None
        self.commands: list[dict[str, Any]] = []
        self.sql_scope: list[str] = []
        self.checks: dict[str, bool] = {}
        self.report: dict[str, Any] = {
            "format": REPORT_FORMAT,
            "scope": (
                "one brand-new private PostgreSQL 14 local Unix-socket cluster; "
                "real Alembic Operations upgrade/downgrade of an existing "
                "dataset_entries table; no TCP, no owner DSN, no Docker, no "
                "provider API, no backend application boot"
            ),
            "not_claimed": [
                "PostgreSQL 16 or any version other than the one reported",
                "all PostgreSQL versions",
                "full application behaviour",
                "crash recovery / durability under an unclean kill",
                "production or shared e2e clusters",
            ],
            "status": "running",
            "checks": self.checks,
            "commands": self.commands,
            "sql_scope": self.sql_scope,
            "started_at": _now(),
        }

    # -- scratch / marker --------------------------------------------------
    def prepare(self) -> None:
        if self.scratch_root_argument:
            root_argument = self.scratch_root_argument
        else:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            root_argument = str(
                self.allowed_root
                / f"atom-pg-lineage-{stamp}-{uuid.uuid4().hex[:8]}")
        self.root = create_scratch_layout(
            root_argument,
            allowed_root=self.allowed_root,
            repo_root=self.repo_root,
        )
        self.report["scratch_root"] = str(self.root)
        self.report["marker_path"] = str(marker_path(self.root))
        self.checks["scratch_safety_prechecked_empty_private"] = True

        cluster_id = uuid.uuid4().hex
        suffix = cluster_id[:8]
        port = choose_port(socket_dir=self.root / SOCKET_DIR_NAME)
        self.marker = {
            "format": MARKER_FORMAT,
            "cluster_id": cluster_id,
            "owned": True,
            "scratch_root": str(self.root),
            "data_directory": str(self.root / "data"),
            "socket_directory": str(self.root / SOCKET_DIR_NAME),
            "port": port,
            "username": f"atom_accept_{suffix}",
            "database": f"atom_accept_db_{suffix}",
            "pg_bindir": str(self.pg_bindir),
            "postgres_version": self._binary_version("postgres"),
            "created_at": _now(),
            "state": "created",
            "pid": None,
            "restarts": [],
        }
        write_marker(self.root, self.marker)

        database_url = str(build_database_url(self.marker))
        self.env = sanitized_environment(self.root, self.pg_bindir, database_url)
        self.report["database_url_redacted"] = database_url
        self.report["environment_keys"] = sorted(self.env)
        self.report["binaries"] = {
            "bindir": str(self.pg_bindir),
            "postgres": self._binary_version("postgres"),
            "initdb": self._binary_version("initdb"),
            "pg_ctl": self._binary_version("pg_ctl"),
        }
        self.report["python"] = {
            "executable": sys.executable,
            "version": sys.version.split()[0],
            "sqlalchemy": sa.__version__,
            "psycopg2": self._module_version("psycopg2"),
        }
        self.report["migration"] = {
            "file": str(MIGRATION_FILE.relative_to(self.repo_root)),
            "sha256": hashlib.sha256(MIGRATION_FILE.read_bytes()).hexdigest(),
        }

    def _binary_version(self, name: str) -> str | None:
        binary = self.pg_bindir / name
        if not binary.is_file():
            return None
        proc = subprocess.run(
            [str(binary), "--version"], capture_output=True, text=True,
            timeout=20, check=False,
        )
        text = (proc.stdout or proc.stderr).strip()
        return text if proc.returncode == 0 else f"unavailable: {text}"

    @staticmethod
    def _module_version(name: str) -> str | None:
        try:
            module = __import__(name)
        except Exception:
            return None
        return getattr(module, "__version__", "present")

    def _require_root(self) -> Path:
        if self.root is None or self.marker is None:
            raise AcceptanceFailure("scratch cluster was not prepared")
        return self.root

    def _update_marker(self, **changes: Any) -> None:
        root = self._require_root()
        assert self.marker is not None
        self.marker.update(changes)
        write_marker(root, self.marker)

    def _reload_marker(self) -> None:
        """Re-read and verify ownership from disk before any lifecycle action."""
        self.marker = load_marker(self._require_root())

    # -- commands ----------------------------------------------------------
    def _run(
        self,
        stage: str,
        argv: Sequence[str],
        *,
        timeout: int = 120,
        log_name: str | None = None,
    ) -> subprocess.CompletedProcess:
        started = time.monotonic()
        try:
            proc = subprocess.run(
                [str(part) for part in argv],
                cwd=str(self.repo_root),
                env=self.env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            self.commands.append({
                "stage": stage,
                "argv": [str(part) for part in argv],
                "timeout_seconds": timeout,
                "exit": None,
                "error": "timeout",
            })
            raise AcceptanceFailure(f"{stage} timed out after {timeout}s") from exc
        record: dict[str, Any] = {
            "stage": stage,
            "argv": [str(part) for part in argv],
            "exit": proc.returncode,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
        if proc.returncode != 0:
            combined = (proc.stdout or "") + (proc.stderr or "")
            record["output_tail"] = combined[-2000:]
        self.commands.append(record)
        if log_name:
            root = self._require_root()
            (root / log_name).write_text(
                (proc.stdout or "") + (proc.stderr or ""), encoding="utf-8")
        if proc.returncode != 0:
            raise AcceptanceFailure(
                f"{stage} failed with exit {proc.returncode}: "
                f"{(proc.stderr or proc.stdout).strip()[-800:]}")
        return proc

    # -- cluster lifecycle -------------------------------------------------
    def init_cluster(self) -> None:
        root = self._require_root()
        assert self.marker is not None
        data_dir = Path(self.marker["data_directory"])
        if data_dir.exists():
            raise SafetyRefusal(f"data directory already exists: {data_dir}")
        initdb = build_initdb_argv(
            self.pg_bindir, data_dir, self.marker["username"])
        self._run("initdb", initdb, timeout=180, log_name="initdb.log")
        if not data_dir.is_dir():
            raise AcceptanceFailure("initdb did not create the data directory")
        config_path = data_dir / "postgresql.conf"
        with config_path.open("a", encoding="utf-8") as handle:
            handle.write(render_cluster_config(
                Path(self.marker["socket_directory"]), self.marker["port"]))
            handle.flush()
            os.fsync(handle.fileno())
        self.report["server_config"] = render_cluster_config(
            Path(self.marker["socket_directory"]), self.marker["port"])
        self._update_marker(state="initialized")

    def start_cluster(self) -> int:
        root = self._require_root()
        self._reload_marker()
        assert self.marker is not None
        data_dir = Path(self.marker["data_directory"])
        if (data_dir / "postmaster.pid").exists():
            raise SafetyRefusal("postmaster.pid already exists; refusing start")
        argv = build_pg_ctl_argv(
            self.pg_bindir, data_dir,
            "-l", str(root / "postgres.log"),
            "-w", "-t", "60",
            "start",
        )
        self._run("pg_ctl start", argv, timeout=120)
        pid = assert_cluster_identity(self.marker)
        listens = tcp_listen_ports(pid)
        if listens:
            raise AcceptanceFailure(
                f"owned postmaster opened TCP LISTEN ports: {listens}")
        private = assert_private_socket(self.marker)
        self._update_marker(state="running", pid=pid)
        self.report["cluster"] = {
            "cluster_id": self.marker["cluster_id"],
            "username": self.marker["username"],
            "database": self.marker["database"],
            "port": self.marker["port"],
            "socket_directory": self.marker["socket_directory"],
            "socket_path": private["socket_file"],
            "socket_directory_mode": private["socket_directory_mode"],
            "socket_file_mode": private["socket_file_mode"],
            "tcp_listen_ports": listens,
            "start_pid": pid,
        }
        return pid

    def stop_cluster(self, *, reason: str) -> int | None:
        root = self._require_root()
        self._reload_marker()
        assert self.marker is not None
        data_dir = Path(self.marker["data_directory"])
        if not (data_dir / "postmaster.pid").exists():
            self._update_marker(state="stopped", stopped_at=_now())
            return None
        pid = assert_cluster_identity(self.marker)
        argv = build_pg_ctl_argv(
            self.pg_bindir, data_dir, "-m", "fast", "-w", "-t", "60", "stop")
        self._run(f"pg_ctl stop ({reason})", argv, timeout=120)
        if (data_dir / "postmaster.pid").exists():
            raise AcceptanceFailure(
                "pg_ctl stop returned but postmaster.pid remains; "
                "refusing to signal any PID")
        if process_matches_cluster(read_process_command(pid), data_dir):
            raise AcceptanceFailure(
                f"PID {pid} still matches this cluster after stop; "
                "refusing a raw-PID kill")
        self._update_marker(
            state="stopped", stopped_at=_now(), last_stopped_pid=pid)
        return pid

    def restart_cluster(self) -> tuple[int, int]:
        self._reload_marker()
        old_pid = assert_cluster_identity(self.marker)
        stopped = self.stop_cluster(reason="restart")
        if stopped is not None and stopped != old_pid:
            raise AcceptanceFailure("restart stopped an unexpected PID")
        new_pid = self.start_cluster()
        if new_pid == old_pid:
            raise AcceptanceFailure(
                f"restart reused PID {new_pid}; cannot prove a new process")
        restarts = list(self.marker.get("restarts") or [])
        restarts.append({
            "old_pid": old_pid,
            "new_pid": new_pid,
            "at": _now(),
            "mode": "clean fast stop + start (not crash recovery)",
        })
        self._update_marker(restarts=restarts)
        self.report["cluster"]["old_pid"] = old_pid
        self.report["cluster"]["new_pid"] = new_pid
        self.report["cluster"]["restart_mode"] = (
            "clean fast stop + start (not crash recovery)")
        return old_pid, new_pid

    # -- database access ---------------------------------------------------
    def connect(self, database: str | None = None) -> sa.Engine:
        assert self.marker is not None
        url = build_database_url(self.marker, database)
        target = assert_socket_only_url(url, self.marker)
        socket_path = socket_file_path(self.marker)
        if not socket_path.exists():
            raise AcceptanceFailure(f"owned Unix socket is missing: {socket_path}")
        engine = sa.create_engine(
            url,
            poolclass=NullPool,
            connect_args={
                "connect_timeout": 5,
                "application_name": "atom-document-lineage-acceptance",
            },
        )
        self.report.setdefault("sql_targets", []).append(target)
        return engine

    def create_database(self, name: str) -> None:
        if not re.fullmatch(r"[a-z0-9_]{1,63}", name):
            raise SafetyRefusal(f"unsafe database name: {name}")
        admin = self.connect("postgres")
        try:
            autocommit = admin.execution_options(
                isolation_level="AUTOCOMMIT")
            with autocommit.connect() as connection:
                connection.execute(sa.text(f'CREATE DATABASE "{name}"'))
        finally:
            admin.dispose()
        self.sql_scope.append(f'CREATE DATABASE "{name}"')

    def verify_server_identity(
        self, engine: sa.Engine, database: str,
    ) -> dict[str, Any]:
        assert self.marker is not None
        with engine.connect() as connection:
            row = connection.execute(sa.text("""
                SELECT current_user,
                       current_database(),
                       current_setting('data_directory') AS data_directory,
                       current_setting('listen_addresses') AS listen_addresses,
                       current_setting('unix_socket_directories')
                           AS unix_socket_directories,
                       current_setting('port') AS port,
                       current_setting('server_version') AS server_version,
                       current_setting('server_version_num')
                           AS server_version_num,
                       inet_server_addr()::text AS tcp_server_address,
                       version() AS version,
                       pg_backend_pid() AS backend_pid
            """)).mappings().one()
        identity = dict(row)
        identity["backend_pid"] = int(identity["backend_pid"])
        if int(identity["port"]) != int(self.marker["port"]):
            raise AcceptanceFailure(
                f"server port {identity['port']} != marker {self.marker['port']}")
        if _resolved(identity["data_directory"]) != _resolved(
                self.marker["data_directory"]):
            raise AcceptanceFailure(
                "connected server data_directory is not this scratch cluster")
        if identity["listen_addresses"] != "":
            raise AcceptanceFailure(
                f"listen_addresses is not disabled: {identity['listen_addresses']!r}")
        sockets = [
            _resolved(part.strip())
            for part in str(identity["unix_socket_directories"]).split(",")
            if part.strip()
        ]
        if _resolved(self.marker["socket_directory"]) not in sockets:
            raise AcceptanceFailure(
                "server does not use this cluster's Unix socket directory")
        if identity["tcp_server_address"] is not None:
            raise AcceptanceFailure(
                f"connection has a TCP server address: {identity['tcp_server_address']}")
        if identity["current_database"] != database:
            raise AcceptanceFailure(
                f"connected database {identity['current_database']} != {database}")
        if identity["current_user"] != self.marker["username"]:
            raise AcceptanceFailure(
                f"connected role {identity['current_user']} is not the cluster role")
        pid = assert_cluster_identity(self.marker)
        listens = tcp_listen_ports(pid)
        if listens:
            raise AcceptanceFailure(
                f"owned postmaster opened TCP LISTEN ports: {listens}")
        identity["tcp_listen_ports"] = listens
        identity["postmaster_pid"] = pid
        self.report["server"] = identity
        self.checks["tcp_disabled_listen_addresses_empty"] = True
        self.checks["connection_uses_owned_unix_socket"] = True
        self.checks["own_cluster_marker_data_directory_verified"] = True
        return identity

    # -- schema inspection -------------------------------------------------
    @staticmethod
    def inspect_schema(engine: sa.Engine) -> dict[str, Any]:
        inspector = sa.inspect(engine)
        columns = {
            column["name"]: {
                "type": str(column["type"]).upper(),
                "nullable": bool(column["nullable"]),
                "default": column.get("default"),
            }
            for column in inspector.get_columns(TABLE)
        }
        indexes = {
            index["name"]: {
                "columns": list(_index_columns(index)),
                "unique": bool(index.get("unique")),
            }
            for index in inspector.get_indexes(TABLE)
        }
        uniques = {
            constraint["name"]: list(constraint["column_names"])
            for constraint in inspector.get_unique_constraints(TABLE)
        }
        with engine.connect() as connection:
            index_rows = connection.execute(sa.text("""
                SELECT c.relname AS name,
                       i.indisunique AS is_unique,
                       i.indisvalid AS is_valid,
                       i.indisready AS is_ready,
                       pg_get_indexdef(i.indexrelid) AS definition,
                       pg_get_expr(i.indpred, i.indrelid) AS predicate
                FROM pg_index i
                JOIN pg_class c ON c.oid = i.indexrelid
                JOIN pg_class t ON t.oid = i.indrelid
                WHERE t.oid = 'public.dataset_entries'::regclass
                ORDER BY c.relname
            """)).mappings().all()
            constraint_rows = connection.execute(sa.text("""
                SELECT conname AS name,
                       contype AS kind,
                       pg_get_constraintdef(oid) AS definition
                FROM pg_constraint
                WHERE conrelid = 'public.dataset_entries'::regclass
                ORDER BY conname
            """)).mappings().all()
            version_rows = connection.execute(sa.text(
                "SELECT version_num FROM alembic_version ORDER BY version_num"
            )).scalars().all()
        return {
            "columns": columns,
            "indexes": indexes,
            "unique_constraints": uniques,
            "pg_indexes": {
                row["name"]: {
                    "unique": bool(row["is_unique"]),
                    "valid": bool(row["is_valid"]),
                    "ready": bool(row["is_ready"]),
                    "definition": row["definition"],
                    "predicate": row["predicate"],
                }
                for row in index_rows
            },
            "constraints": {
                row["name"]: {
                    "kind": row["kind"],
                    "definition": row["definition"],
                }
                for row in constraint_rows
            },
            "alembic_versions": list(version_rows),
        }

    # -- data helpers ------------------------------------------------------
    @staticmethod
    def _row_select(where: str = "") -> str:
        return (
            "SELECT " + ", ".join(OLD_COLUMNS) + f" FROM {TABLE} "
            + where + " ORDER BY id"
        )

    def snapshot(self, engine: sa.Engine, *, only_seed: bool = False
                 ) -> list[dict[str, Any]]:
        with engine.connect() as connection:
            if only_seed:
                rows = connection.execute(
                    sa.text(self._row_select(
                        "WHERE id = ANY(:ids)")),
                    {"ids": list(SEED_IDS)},
                ).mappings().all()
            else:
                rows = connection.execute(
                    sa.text(self._row_select())).mappings().all()
        return _canonical_rows(rows)

    @staticmethod
    def assert_same_rows(
        stage: str, before: Sequence[Mapping[str, Any]],
        after: Sequence[Mapping[str, Any]],
    ) -> str:
        before_digest = canonical_digest(list(before))
        after_digest = canonical_digest(list(after))
        if before_digest != after_digest or list(before) != list(after):
            raise AcceptanceFailure(
                f"{stage}: stored rows changed "
                f"(before {before_digest}, after {after_digest})")
        return after_digest

    # -- migration ---------------------------------------------------------
    def run_migration(self, direction: str) -> None:
        assert self.engine is not None
        if direction not in {"upgrade", "downgrade"}:
            raise ValueError(direction)
        MigrationContext, Operations = load_alembic_runtime()
        with self.engine.begin() as connection:
            context = MigrationContext.configure(
                connection, opts={"version_table": "alembic_version"})
            with Operations.context(context):
                getattr(self.migration, direction)()
        self.sql_scope.append(f"alembic Operations {direction}()")

    def read_revision(self) -> str | None:
        assert self.engine is not None
        with self.engine.connect() as connection:
            return connection.execute(sa.text(
                "SELECT version_num FROM alembic_version"
            )).scalar_one_or_none()

    def stamp_revision(self, old: str, new: str) -> None:
        assert self.engine is not None
        with self.engine.begin() as connection:
            result = connection.execute(
                sa.text(
                    "UPDATE alembic_version SET version_num = :new "
                    "WHERE version_num = :old"),
                {"new": new, "old": old},
            )
            if result.rowcount != 1:
                raise AcceptanceFailure(
                    f"could not label migration revision {old} -> {new} "
                    f"(rowcount {result.rowcount})")
        self.sql_scope.append(
            f"UPDATE alembic_version {old} -> {new} (direct revision label)")

    def create_legacy_schema(self) -> None:
        assert self.engine is not None
        with self.engine.begin() as connection:
            connection.execute(sa.text(LEGACY_CREATE_SQL))
            for name, columns in LEGACY_INDEXES.items():
                connection.execute(sa.text(
                    f"CREATE INDEX {name} ON {TABLE} ({', '.join(columns)})"))
            connection.execute(sa.text(
                "CREATE TABLE alembic_version "
                "(version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
            connection.execute(
                sa.text(
                    "INSERT INTO alembic_version (version_num) VALUES (:rev)"),
                {"rev": PRE_REVISION},
            )
            for row in SEED_ROWS:
                connection.execute(INSERT_ROW_SQL, dict(row))
        self.sql_scope.extend([
            f"CREATE TABLE {TABLE} (pre-lineage shape + named UNIQUE)",
            "CREATE INDEX x5 (workspace/tenant/created_by/external_id/"
            "dataset_name)",
            f"CREATE INDEX {FILE_LOOKUP_INDEX} (source, external_id, status)",
            "CREATE TABLE alembic_version (VARCHAR(32) PRIMARY KEY)",
            f"INSERT seed rows ({len(SEED_ROWS)})",
        ])

    def enforce_unique(self) -> dict[str, Any]:
        assert self.engine is not None
        duplicate = dict(SEED_ROWS[0])
        duplicate["id"] = f"seed-duplicate-{uuid.uuid4().hex[:6]}"
        try:
            with self.engine.begin() as connection:
                connection.execute(INSERT_ROW_SQL, duplicate)
        except sa.exc.IntegrityError as exc:
            constraint = None
            diag = getattr(getattr(exc, "orig", None), "diag", None)
            if diag is not None:
                constraint = getattr(diag, "constraint_name", None)
            return {
                "rejected": True,
                "constraint": constraint,
                "sqlstate": getattr(
                    getattr(exc, "orig", None), "pgcode", None),
            }
        raise AcceptanceFailure(
            "duplicate rows were accepted; uq_dataset_entries_version lost")

    def write_lineage(self, row_id: str, document_id: str) -> None:
        assert self.engine is not None
        with self.engine.begin() as connection:
            result = connection.execute(
                sa.text(
                    f"UPDATE {TABLE} SET {COLUMN} = :doc WHERE id = :id"),
                {"doc": document_id, "id": row_id},
            )
            if result.rowcount != 1:
                raise AcceptanceFailure(
                    f"lineage update touched {result.rowcount} rows for {row_id}")
        with self.engine.connect() as connection:
            stored = connection.execute(
                sa.text(f"SELECT {COLUMN} FROM {TABLE} WHERE id = :id"),
                {"id": row_id},
            ).scalar_one()
        if stored != document_id:
            raise AcceptanceFailure(
                f"lineage read-back mismatch: {stored!r} != {document_id!r}")

    def insert_lineage_row(self, document_id: str) -> dict[str, Any]:
        assert self.engine is not None
        row = dict(SEED_ROWS[3])
        row.update({
            "id": NEW_LINEAGE_ROW_ID,
            "source": "upload",
            "external_id": f"lineage-new-{uuid.uuid4().hex[:6]}",
            "file_name": "lineage-new.csv",
            "content_hash": f"hash-lineage-{uuid.uuid4().hex[:6]}",
            "entity_name": "lineage_new",
            "dataset_name": "lineage_new",
            "parquet_path": "/scratch/acceptance/lineage-new.parquet",
            "source_modified_at": "2026-11-17T09:00:00+00:00",
            "ingested_at": "2026-11-17T09:00:01+00:00",
        })
        columns = list(OLD_COLUMNS) + [COLUMN]
        params = dict(row)
        params[COLUMN] = document_id
        statement = sa.text(
            f"INSERT INTO {TABLE} ({', '.join(columns)}) VALUES ("
            + ", ".join(
                f"CAST(:{name} AS JSON)" if name == "columns_json"
                else (
                    f"CAST(:{name} AS TIMESTAMP WITH TIME ZONE)"
                    if name in {"source_modified_at", "ingested_at"}
                    else f":{name}"
                )
                for name in columns
            ) + ")"
        )
        with self.engine.begin() as connection:
            connection.execute(statement, params)
        with self.engine.connect() as connection:
            stored = connection.execute(
                sa.text(f"SELECT {COLUMN} FROM {TABLE} WHERE id = :id"),
                {"id": NEW_LINEAGE_ROW_ID},
            ).scalar_one()
        if stored != document_id:
            raise AcceptanceFailure(
                "new lineage row did not store source_document_id")
        return {"id": NEW_LINEAGE_ROW_ID, "source_document_id": stored}

    def create_legacy_table_for_fresh_guard(self, database: str) -> None:
        engine = self.connect(database)
        try:
            with engine.begin() as connection:
                connection.execute(sa.text(
                    "CREATE TABLE unrelated (id VARCHAR PRIMARY KEY)"))
        finally:
            engine.dispose()

    # -- main contract -----------------------------------------------------
    def run(self) -> None:
        self.prepare()
        self.init_cluster()
        self.start_cluster()
        self.create_database(self.marker["database"])

        self.engine = self.connect(self.marker["database"])
        try:
            self.verify_server_identity(self.engine, self.marker["database"])
            self.migration = load_migration()
            if self.migration.revision != MIGRATION_REVISION:
                raise AcceptanceFailure(
                    f"migration revision {self.migration.revision!r} is not "
                    f"{MIGRATION_REVISION!r}")
            if self.migration.down_revision != PRE_REVISION:
                raise AcceptanceFailure(
                    f"migration down_revision {self.migration.down_revision!r} "
                    f"is not {PRE_REVISION!r}")
            self.checks["migration_revision_chain_loaded"] = True

            self.create_legacy_schema()
            before_all = self.snapshot(self.engine)
            before_seed = self.snapshot(self.engine, only_seed=True)
            before_schema = self.inspect_schema(self.engine)
            if len(before_all) != len(SEED_ROWS):
                raise AcceptanceFailure("legacy seed row count is wrong")
            if set(before_schema["columns"]) != set(OLD_COLUMNS):
                raise AcceptanceFailure(
                    "legacy table does not have exactly the pre-lineage columns")
            self.report["before"] = {
                "row_count": len(before_all),
                "seed_digest": canonical_digest(before_seed),
                "all_digest": canonical_digest(before_all),
                "columns": sorted(before_schema["columns"]),
                "indexes": {
                    name: list(info["columns"])
                    for name, info in before_schema["indexes"].items()
                },
                "unique_constraints": before_schema["unique_constraints"],
                "alembic_versions": before_schema["alembic_versions"],
            }

            # 1. Real upgrade through Alembic Operations.
            self.run_migration("upgrade")
            self.stamp_revision(PRE_REVISION, MIGRATION_REVISION)
            if self.read_revision() != MIGRATION_REVISION:
                raise AcceptanceFailure("direct revision label was not stored")

            after_all = self.snapshot(self.engine)
            after_seed = self.snapshot(self.engine, only_seed=True)
            self.assert_same_rows("upgrade", before_all, after_all)
            self.assert_same_rows("upgrade seed", before_seed, after_seed)
            self.checks["legacy_rows_unchanged_after_upgrade"] = True

            after_schema = self.inspect_schema(self.engine)
            lineage_column = after_schema["columns"].get(COLUMN)
            if lineage_column is None:
                raise AcceptanceFailure("source_document_id column is missing")
            if lineage_column["nullable"] is not True:
                raise AcceptanceFailure("source_document_id is not nullable")
            if "VARCHAR" not in lineage_column["type"]:
                raise AcceptanceFailure(
                    f"source_document_id type is {lineage_column['type']}")
            if lineage_column["default"] not in (None, ""):
                raise AcceptanceFailure(
                    f"source_document_id has a default: {lineage_column['default']}")
            for name in OLD_COLUMNS:
                if after_schema["columns"].get(name) != before_schema["columns"].get(name):
                    raise AcceptanceFailure(
                        f"legacy column {name} changed shape")
            self.checks["lineage_column_added_nullable_no_backfill"] = True

            lineage_index = after_schema["indexes"].get(INDEX)
            if lineage_index is None:
                raise AcceptanceFailure(f"index {INDEX} is missing")
            if lineage_index["unique"]:
                raise AcceptanceFailure(f"index {INDEX} must be non-unique")
            if lineage_index["columns"] != [COLUMN]:
                raise AcceptanceFailure(
                    f"index {INDEX} columns are {lineage_index['columns']}")
            pg_index = after_schema["pg_indexes"].get(INDEX, {})
            if not (pg_index.get("valid") and pg_index.get("ready")
                    and not pg_index.get("unique")):
                raise AcceptanceFailure(
                    f"index {INDEX} is not a valid non-unique index: {pg_index}")
            for name, columns in LEGACY_INDEXES.items():
                actual = after_schema["indexes"].get(name)
                if actual is None or actual["columns"] != list(columns):
                    raise AcceptanceFailure(
                        f"legacy index {name} changed: {actual}")
                definition = after_schema["pg_indexes"].get(name, {}).get(
                    "definition")
                if definition != before_schema["pg_indexes"].get(
                        name, {}).get("definition"):
                    raise AcceptanceFailure(
                        f"legacy index {name} was rebuilt/redefined")
            self.checks["lineage_index_added_valid_nonunique"] = True
            self.checks["preexisting_indexes_preserved"] = True

            if after_schema["unique_constraints"] != {
                    "uq_dataset_entries_version": [
                        "source_kind", "source", "external_id",
                        "content_hash", "entity_name"]}:
                raise AcceptanceFailure(
                    "uq_dataset_entries_version shape changed")
            if after_schema["constraints"] != before_schema["constraints"]:
                raise AcceptanceFailure(
                    "table constraints changed beyond adding the column")
            self.checks["unique_constraint_preserved"] = True
            unique_proof = self.enforce_unique()
            if not unique_proof["rejected"]:
                raise AcceptanceFailure("duplicate row was not rejected")
            self.checks["unique_constraint_still_enforced"] = True

            self.write_lineage("seed-active", "doc-acceptance-upgrade-1")
            self.checks["lineage_writable_after_upgrade"] = True

            # 2. Idempotent re-run.
            self.run_migration("upgrade")
            self.run_migration("upgrade")
            after_repeat = self.inspect_schema(self.engine)
            if sum(1 for name in after_repeat["columns"] if name == COLUMN) != 1:
                raise AcceptanceFailure("repeat upgrade duplicated the column")
            if [name for name in after_repeat["indexes"] if name == INDEX] != [
                    INDEX]:
                raise AcceptanceFailure("repeat upgrade duplicated the index")
            self.assert_same_rows(
                "repeat upgrade", before_seed,
                self.snapshot(self.engine, only_seed=True))
            with self.engine.connect() as connection:
                first_lineage = connection.execute(sa.text(
                    f"SELECT {COLUMN} FROM {TABLE} WHERE id = 'seed-active'"
                )).scalar_one()
            if first_lineage != "doc-acceptance-upgrade-1":
                raise AcceptanceFailure("repeat upgrade changed lineage data")
            self.checks["upgrade_idempotent_on_upgraded_table"] = True

            # 3. Partial state: missing index is repaired without row changes.
            with self.engine.begin() as connection:
                connection.execute(sa.text(f"DROP INDEX {INDEX}"))
            if INDEX in self.inspect_schema(self.engine)["indexes"]:
                raise AcceptanceFailure("could not drop index for repair test")
            self.run_migration("upgrade")
            repaired = self.inspect_schema(self.engine)
            repaired_index = repaired["pg_indexes"].get(INDEX, {})
            if not repaired_index.get("valid"):
                raise AcceptanceFailure("upgrade did not repair the missing index")
            self.assert_same_rows(
                "partial index repair", before_seed,
                self.snapshot(self.engine, only_seed=True))
            self.checks["partial_upgrade_repairs_missing_index"] = True

            # 4. Downgrade removes only the lineage upgrade.
            self.run_migration("downgrade")
            self.stamp_revision(MIGRATION_REVISION, PRE_REVISION)
            downgraded = self.inspect_schema(self.engine)
            if COLUMN in downgraded["columns"]:
                raise AcceptanceFailure("downgrade left source_document_id")
            if INDEX in downgraded["indexes"]:
                raise AcceptanceFailure("downgrade left the lineage index")
            self.assert_same_rows(
                "downgrade", before_seed,
                self.snapshot(self.engine, only_seed=True))
            for name, columns in LEGACY_INDEXES.items():
                actual = downgraded["indexes"].get(name)
                if actual is None or actual["columns"] != list(columns):
                    raise AcceptanceFailure(
                        f"downgrade changed legacy index {name}: {actual}")
            if downgraded["unique_constraints"] != {
                    "uq_dataset_entries_version": [
                        "source_kind", "source", "external_id",
                        "content_hash", "entity_name"]}:
                raise AcceptanceFailure(
                    "downgrade changed the version unique constraint")
            if downgraded["constraints"] != before_schema["constraints"]:
                raise AcceptanceFailure(
                    "downgrade changed legacy table constraints")
            pre_downgrade_unique = self.enforce_unique()
            if not pre_downgrade_unique["rejected"]:
                raise AcceptanceFailure(
                    "unique constraint lost after downgrade")
            if self.read_revision() != PRE_REVISION:
                raise AcceptanceFailure("downgrade revision label is wrong")
            self.checks["downgrade_removes_only_lineage_upgrade"] = True
            self.checks["downgrade_preserves_rows_indexes_constraints"] = True
            self.report["downgrade"] = {
                "column_removed": True,
                "index_removed": True,
                "lineage_values_dropped_with_column": True,
                "rows_unchanged": True,
                "revision": PRE_REVISION,
            }

            # 5. Re-upgrade and write fresh lineage (update + new row).
            self.run_migration("upgrade")
            self.stamp_revision(PRE_REVISION, MIGRATION_REVISION)
            reupgraded = self.inspect_schema(self.engine)
            if reupgraded["columns"].get(COLUMN, {}).get("nullable") is not True:
                raise AcceptanceFailure("re-upgrade did not restore the column")
            if INDEX not in reupgraded["indexes"]:
                raise AcceptanceFailure("re-upgrade did not restore the index")
            self.assert_same_rows(
                "re-upgrade", before_seed,
                self.snapshot(self.engine, only_seed=True))
            self.write_lineage("seed-active", "doc-acceptance-upgrade-2")
            new_row = self.insert_lineage_row("doc-acceptance-new-row")
            self.checks["downgrade_then_reupgrade_restores_lineage"] = True
            self.checks["new_lineage_row_writable"] = True

            # 6. Restart only this cluster and read through a new connection.
            restart_unique = self.enforce_unique()
            if not restart_unique["rejected"]:
                raise AcceptanceFailure("unique constraint lost before restart")
            old_pid, new_pid = self.restart_cluster()
            self.engine.dispose()
            self.engine = self.connect(self.marker["database"])
            self.verify_server_identity(self.engine, self.marker["database"])
            post_restart_seed = self.snapshot(self.engine, only_seed=True)
            self.assert_same_rows(
                "post-restart", before_seed, post_restart_seed)
            with self.engine.connect() as connection:
                restored_lineage = connection.execute(sa.text(
                    f"SELECT {COLUMN} FROM {TABLE} WHERE id = 'seed-active'"
                )).scalar_one()
                restored_new_lineage = connection.execute(sa.text(
                    f"SELECT {COLUMN} FROM {TABLE} WHERE id = :id"),
                    {"id": NEW_LINEAGE_ROW_ID},
                ).scalar_one()
            if restored_lineage != "doc-acceptance-upgrade-2":
                raise AcceptanceFailure(
                    "lineage did not survive the cluster restart")
            if restored_new_lineage != new_row["source_document_id"]:
                raise AcceptanceFailure(
                    "new lineage row did not survive the cluster restart")
            post_restart_unique = self.enforce_unique()
            if not post_restart_unique["rejected"]:
                raise AcceptanceFailure(
                    "unique constraint lost after restart")
            self.checks["restart_used_new_owned_postmaster_pid"] = True
            self.checks["post_restart_rows_lineage_and_unique_persisted"] = True
            self.report["restart"] = {
                "old_pid": old_pid,
                "new_pid": new_pid,
                "mode": "clean fast stop + start (not crash recovery)",
                "data_directory": self.marker["data_directory"],
                "lineage_after_restart": restored_lineage,
                "new_row_lineage_after_restart": restored_new_lineage,
                "unique_constraint_after_restart": post_restart_unique,
            }

            # 7. Absent-table guard in a separate database on the same cluster.
            fresh_database = f"{self.marker['database']}_fresh"
            self.create_database(fresh_database)
            self.create_legacy_table_for_fresh_guard(fresh_database)
            fresh_engine = self.connect(fresh_database)
            try:
                MigrationContext, Operations = load_alembic_runtime()
                with fresh_engine.begin() as connection:
                    context = MigrationContext.configure(connection)
                    with Operations.context(context):
                        self.migration.upgrade()
                        self.migration.upgrade()
                        self.migration.downgrade()
                fresh_tables = set(sa.inspect(fresh_engine).get_table_names())
                if TABLE in fresh_tables:
                    raise AcceptanceFailure(
                        "absent-table guard created dataset_entries")
                if INDEX in {
                    index["name"] for index in
                    sa.inspect(fresh_engine).get_indexes("unrelated")
                }:
                    raise AcceptanceFailure(
                        "absent-table guard created the lineage index")
            finally:
                fresh_engine.dispose()
            self.sql_scope.append(
                "fresh database: Operations upgrade()x2 + downgrade() no-op")
            self.checks["absent_table_guard_is_safe_noop"] = True

            self.report["after"] = {
                "seed_digest": canonical_digest(
                    self.snapshot(self.engine, only_seed=True)),
                "row_count": len(self.snapshot(self.engine)),
                "lineage_values": {
                    "seed-active": restored_lineage,
                    NEW_LINEAGE_ROW_ID: restored_new_lineage,
                },
                "constraints": reupgraded["constraints"],
                "unique_constraints": reupgraded["unique_constraints"],
                "lineage_index": reupgraded["pg_indexes"].get(INDEX),
                "alembic_versions": [self.read_revision()],
                "unique_proofs": [
                    unique_proof, pre_downgrade_unique,
                    restart_unique, post_restart_unique,
                ],
            }
            self.checks["proof_digest_recorded"] = True
            self.report["proof_digest"] = canonical_digest({
                "format": REPORT_FORMAT,
                "checks": self.checks,
                "before": self.report["before"],
                "after": self.report["after"],
                "server": self.report["server"],
                "restart": self.report["restart"],
            })
        finally:
            if self.engine is not None:
                self.engine.dispose()
                self.engine = None

    # -- cleanup / report --------------------------------------------------
    def cleanup(self) -> bool:
        cleanup: dict[str, Any] = {
            "attempted": True,
            "scratch_root_preserved": True,
            "recursive_delete_performed": False,
        }
        self.report["cleanup"] = cleanup
        if self.root is None:
            cleanup.update({"stopped": True, "reason": "nothing prepared"})
            return True
        cleanup["preserved_paths"] = [
            str(self.root),
            str(self.root / "data"),
            str(self.root / "sock"),
        ]
        if self.marker is None:
            cleanup.update({
                "stopped": False,
                "reason": "no ownership marker; refusing any process action",
            })
            return True
        try:
            self._reload_marker()
            verify_marker(self.marker, self.root)
            data_dir = Path(self.marker["data_directory"])
            if not (data_dir / "postmaster.pid").exists():
                cleanup.update({
                    "stopped": True,
                    "reason": "no postmaster.pid for this cluster",
                })
                return True
            pid = assert_cluster_identity(self.marker)
            stopped = self.stop_cluster(reason="acceptance cleanup")
            cleanup.update({
                "stopped": True,
                "pid": stopped,
                "reason": "pg_ctl -D <owned data> -m fast -w stop",
                "postmaster_pid_absent": not (
                    data_dir / "postmaster.pid").exists(),
            })
            return True
        except Exception as exc:  # noqa: BLE001 - reported, never raw-killed
            data_dir = Path(self.marker["data_directory"])
            pidfile_absent = not (data_dir / "postmaster.pid").exists()
            marker_pid = self.marker.get("pid") or self.marker.get(
                "last_stopped_pid")
            still_matches = bool(
                isinstance(marker_pid, int)
                and process_matches_cluster(
                    read_process_command(marker_pid), data_dir))
            cleanup.update({
                "stopped": pidfile_absent and not still_matches,
                "error_class": type(exc).__name__,
                "error": str(exc)[:800],
                "reason": (
                    "identity/stop verification failed; no raw-PID kill"
                    if not (pidfile_absent and not still_matches)
                    else "postmaster already absent after an errored stop"),
            })
            return pidfile_absent and not still_matches

    def write_report(self, outcome: str, error: BaseException | None) -> Path | None:
        self.report["status"] = outcome
        self.report["finished_at"] = _now()
        self.report["checks"] = self.checks
        self.report["checks_all_passed"] = bool(self.checks) and all(
            self.checks.values())
        if error is not None:
            self.report["error"] = {
                "class": type(error).__name__,
                "message": str(error)[:2000],
            }
        if self.root is None:
            return None
        path = self.root / "report.json"
        path.write_text(
            json.dumps(self.report, indent=2, sort_keys=True, default=_json_default)
            + "\n",
            encoding="utf-8",
        )
        os.chmod(path, 0o600)
        return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the 20261117 dataset_entries document-lineage migration "
            "against a brand-new private PostgreSQL Unix-socket cluster."
        ),
    )
    parser.add_argument(
        "--scratch-root",
        default=None,
        help=(
            "Brand-new/empty absolute scratch directory under /private/tmp. "
            "Defaults to a unique new directory."
        ),
    )
    parser.add_argument(
        "--pg-bindir",
        default=str(DEFAULT_PG_BINDIR),
        help="Directory containing initdb/pg_ctl/postgres (default: /usr/local/bin).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    harness = AcceptanceHarness(
        args.scratch_root, pg_bindir=args.pg_bindir)
    outcome = "failed"
    error: BaseException | None = None
    cleanup_ok = False
    try:
        harness.run()
        outcome = "passed"
    except SafetyRefusal as exc:
        error = exc
        outcome = "refused"
        print(f"REFUSED: {exc}", file=sys.stderr)
        # Nothing is created for the documented refusal cases. If a later
        # lifecycle step refused (e.g. pidfile already present), preserve it.
    except BaseException as exc:  # noqa: BLE001 - reported with cleanup
        error = exc
        outcome = "failed"
        print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
    finally:
        cleanup_ok = harness.cleanup()

    if outcome == "refused" and harness.root is None:
        return 2
    if outcome == "passed" and not cleanup_ok:
        outcome = "failed"
        error = AcceptanceFailure(
            "acceptance checks passed but owned-server cleanup was not proven")
    report_path = harness.write_report(outcome, error)
    if report_path is not None:
        sys.stdout.write(report_path.read_text(encoding="utf-8"))
    return 0 if outcome == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
