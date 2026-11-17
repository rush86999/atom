"""Safety and contract tests for the real-PostgreSQL lineage acceptance.

The harness in ``scripts/acceptance/postgres_document_lineage_upgrade.py``
creates a brand-new private PostgreSQL cluster. That is exactly the kind of
tool that must fail closed: a mistaken scratch path could point at the repo,
a live database or a symlink, and a mistaken PID check could stop somebody
else's server.

These tests therefore concentrate on the refusal paths, using no database at
all: non-empty roots, symlinks, protected locations, unsafe ports/DSNs,
foreign PID command lines and corrupted ownership markers. The migration's
revision/orm contract is checked without a connection too. The one real
cluster contract is opt-in so a normal pytest run stays database-free::

    ATOM_PG_LINEAGE_ACCEPTANCE_REAL=1 \
      pytest backend/tests/test_postgres_document_lineage_upgrade_acceptance.py

The opt-in test invokes the public harness as a user would and reads its
JSON report; it does not reimplement the upgrade.
"""
from __future__ import annotations

import importlib.util
import json
import os
import random
import stat
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa

REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS_PATH = (
    REPO_ROOT
    / "scripts/acceptance/postgres_document_lineage_upgrade.py"
)
MIGRATION_PATH = (
    REPO_ROOT
    / "backend/alembic/versions/20261117_dataset_entry_source_document.py"
)


def _load_harness():
    spec = importlib.util.spec_from_file_location(
        "atom_postgres_document_lineage_acceptance_harness", HARNESS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harness = _load_harness()


def _real_tmp_root(_tmp_path: Path) -> Path:
    """A short real-path base under /private/tmp.

    The production socket-path limit is real (macOS ``sun_path``), so pytest's
    long per-test basetemp cannot be used here: the safety check must be
    exercised against a path shape the harness would actually accept. The
    directory is deliberately tiny and unique; it is evidence only and is not
    recursively deleted.
    """
    base = Path("/private/tmp") / f"alp-{uuid.uuid4().hex[:12]}"
    base.mkdir(mode=0o700)
    allowed = base / "a"
    allowed.mkdir(mode=0o700)
    return allowed


def _marker(root: Path, *, port: int = 24680) -> dict:
    return {
        "format": harness.MARKER_FORMAT,
        "cluster_id": uuid.uuid4().hex,
        "owned": True,
        "scratch_root": str(root),
        "data_directory": str(root / "data"),
        "socket_directory": str(root / "sock"),
        "port": port,
        "username": "atom_accept_test",
        "database": "atom_accept_db_test",
        "pg_bindir": "/usr/local/bin",
        "postgres_version": "test-only",
        "state": "created",
        "pid": None,
        "restarts": [],
    }


def _prepared_root(tmp_path: Path) -> tuple[Path, Path]:
    allowed = _real_tmp_root(tmp_path)
    root = harness.create_scratch_layout(
        allowed / "fresh-cluster", allowed_root=allowed)
    return allowed, root


# ---------------------------------------------------------------------------
# Scratch-root safety (no mkdir / no database on refusal)
# ---------------------------------------------------------------------------
def test_relative_scratch_root_is_refused_without_creation(tmp_path):
    allowed = _real_tmp_root(tmp_path)
    with pytest.raises(harness.SafetyRefusal):
        harness.validate_scratch_root(
            "relative-scratch", allowed_root=allowed)
    assert not (allowed / "relative-scratch").exists()


def test_scratch_root_outside_allowed_root_is_refused(tmp_path):
    base = Path(os.path.realpath(tmp_path))
    allowed = base / "allowed"
    allowed.mkdir()
    outside = base / "outside"
    with pytest.raises(harness.SafetyRefusal):
        harness.validate_scratch_root(outside, allowed_root=allowed)
    assert not outside.exists()


def test_allowed_root_itself_is_refused(tmp_path):
    allowed = _real_tmp_root(tmp_path)
    with pytest.raises(harness.SafetyRefusal):
        harness.validate_scratch_root(allowed, allowed_root=allowed)


def test_protected_repo_and_explicit_paths_are_refused(tmp_path):
    allowed = _real_tmp_root(tmp_path)
    repo = allowed / "repo"
    repo.mkdir()
    with pytest.raises(harness.SafetyRefusal):
        harness.validate_scratch_root(
            repo / "scratch", allowed_root=allowed, repo_root=repo)

    explicit = allowed / "protected"
    explicit.mkdir()
    with pytest.raises(harness.SafetyRefusal):
        harness.validate_scratch_root(
            explicit / "scratch",
            allowed_root=allowed,
            protected_paths=[explicit],
        )
    assert not (explicit / "scratch").exists()


def test_nonempty_scratch_root_is_refused_and_left_untouched(tmp_path):
    allowed = _real_tmp_root(tmp_path)
    root = allowed / "nonempty"
    root.mkdir()
    sentinel = root / "OWNER-EVIDENCE.txt"
    sentinel.write_text("do not touch\n", encoding="utf-8")
    before = sorted(path.name for path in root.iterdir())

    with pytest.raises(harness.SafetyRefusal):
        harness.validate_scratch_root(root, allowed_root=allowed)
    with pytest.raises(harness.SafetyRefusal):
        harness.create_scratch_layout(root, allowed_root=allowed)

    assert sentinel.read_text(encoding="utf-8") == "do not touch\n"
    assert sorted(path.name for path in root.iterdir()) == before
    assert not (root / "data").exists()
    assert not (root / "sock").exists()


def test_symlink_scratch_root_is_refused_and_target_untouched(tmp_path):
    allowed = _real_tmp_root(tmp_path)
    target = allowed / "target"
    target.mkdir()
    link = allowed / "link"
    link.symlink_to(target, target_is_directory=True)

    with pytest.raises(harness.SafetyRefusal):
        harness.validate_scratch_root(link, allowed_root=allowed)
    with pytest.raises(harness.SafetyRefusal):
        harness.create_scratch_layout(link, allowed_root=allowed)

    assert list(target.iterdir()) == []


def test_symlinked_parent_is_refused_before_mkdir(tmp_path):
    allowed = _real_tmp_root(tmp_path)
    shared = allowed / "shared"
    shared.mkdir()
    parent = allowed / "aliased-parent"
    parent.symlink_to(shared, target_is_directory=True)

    with pytest.raises(harness.SafetyRefusal):
        harness.validate_scratch_root(
            parent / "would-be-cluster", allowed_root=allowed)
    assert list(shared.iterdir()) == []


def test_regular_file_scratch_root_is_refused(tmp_path):
    allowed = _real_tmp_root(tmp_path)
    root = allowed / "file-not-dir"
    root.write_text("not a directory", encoding="utf-8")
    with pytest.raises(harness.SafetyRefusal):
        harness.validate_scratch_root(root, allowed_root=allowed)
    assert root.read_text(encoding="utf-8") == "not a directory"


def test_too_long_socket_path_is_refused(tmp_path):
    allowed = _real_tmp_root(tmp_path)
    candidate = allowed / ("x" * 80)
    with pytest.raises(harness.SafetyRefusal):
        harness.validate_scratch_root(candidate, allowed_root=allowed)
    assert not candidate.exists()


def test_fresh_root_is_not_created_by_validation_then_is_private(tmp_path):
    allowed = _real_tmp_root(tmp_path)
    candidate = allowed / "fresh"
    validated = harness.validate_scratch_root(
        candidate, allowed_root=allowed)
    assert validated == candidate.resolve()
    assert not candidate.exists()

    root = harness.create_scratch_layout(candidate, allowed_root=allowed)
    assert root == candidate.resolve()
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    for name in ("sock", "home", "tmp"):
        child = root / name
        assert child.is_dir()
        assert stat.S_IMODE(child.stat().st_mode) == 0o700
    assert not (root / "data").exists()
    assert sorted(path.name for path in root.iterdir()) == ["home", "sock", "tmp"]


# ---------------------------------------------------------------------------
# Marker / PID identity (never stop a foreign process)
# ---------------------------------------------------------------------------
def test_marker_roundtrip_and_tampering_is_refused(tmp_path):
    _, root = _prepared_root(tmp_path)
    marker = _marker(root)
    harness.write_marker(root, marker)
    assert harness.load_marker(root)["cluster_id"] == marker["cluster_id"]

    tampered = dict(marker)
    tampered["data_directory"] = str(root.parent / "elsewhere" / "data")
    harness.write_marker(root, tampered)
    with pytest.raises(harness.SafetyRefusal):
        harness.load_marker(root)

    tampered = dict(marker)
    tampered["owned"] = False
    harness.write_marker(root, tampered)
    with pytest.raises(harness.SafetyRefusal):
        harness.load_marker(root)

    tampered = dict(marker)
    tampered["port"] = 5432
    harness.write_marker(root, tampered)
    with pytest.raises(harness.SafetyRefusal):
        harness.load_marker(root)


def test_marker_symlink_is_refused(tmp_path):
    _, root = _prepared_root(tmp_path)
    marker = _marker(root)
    harness.write_marker(root, marker)
    real_marker = harness.marker_path(root)
    moved = root / "moved-marker.json"
    real_marker.rename(moved)
    real_marker.symlink_to(moved)
    with pytest.raises(harness.SafetyRefusal):
        harness.load_marker(root)


def test_process_command_requires_exact_cluster_data_directory(tmp_path):
    data = tmp_path / "cluster" / "data"
    data.mkdir(parents=True)
    assert harness.process_matches_cluster(
        f"/usr/local/bin/postgres -D {data} -k /tmp/sock", data)
    assert harness.process_matches_cluster(
        f"/usr/local/bin/postgres -D{data}", data)
    assert harness.process_matches_cluster(
        f"/usr/local/bin/postgres -D '{data}'", data)
    assert not harness.process_matches_cluster(
        f"/usr/local/bin/postgres -D {data}-other", data)
    assert not harness.process_matches_cluster(
        f"/usr/local/bin/postgres -D {data}/../data-other", data)
    assert not harness.process_matches_cluster(
        "/usr/local/bin/postgres -D /var/lib/postgresql/data", data)
    assert not harness.process_matches_cluster("", data)
    assert not harness.process_matches_cluster(None, data)


def test_pg_ctl_status_pid_parser():
    assert harness.parse_pg_ctl_pid(
        "pg_ctl: server is running (PID: 4242)\n"
        "/usr/local/bin/postgres -D /private/tmp/x/data") == 4242
    assert harness.parse_pg_ctl_pid(
        "pg_ctl: server is running (PID: 7)") == 7
    assert harness.parse_pg_ctl_pid("no server running") is None
    assert harness.parse_pg_ctl_pid(None) is None


def test_cluster_identity_refuses_foreign_or_mismatched_process(tmp_path):
    _, root = _prepared_root(tmp_path)
    data = root / "data"
    data.mkdir()
    marker = _marker(root)
    owned_command = f"/usr/local/bin/postgres -D {data}"
    status = "pg_ctl: server is running (PID: 4242)\n"

    assert harness.assert_cluster_identity(
        marker,
        pidfile_pid=4242,
        process_command=owned_command,
        status_output=status,
    ) == 4242

    with pytest.raises(harness.SafetyRefusal):
        harness.assert_cluster_identity(
            marker,
            pidfile_pid=4242,
            process_command="/usr/local/bin/postgres -D /foreign/data",
            status_output=status,
        )
    with pytest.raises(harness.SafetyRefusal):
        harness.assert_cluster_identity(
            marker,
            expected_pid=9999,
            pidfile_pid=4242,
            process_command=owned_command,
            status_output=status,
        )
    with pytest.raises(harness.SafetyRefusal):
        harness.assert_cluster_identity(
            marker,
            pidfile_pid=4242,
            process_command=owned_command,
            status_output="pg_ctl: server is running (PID: 9999)",
        )
    with pytest.raises(harness.SafetyRefusal):
        harness.assert_cluster_identity(
            marker,
            pidfile_pid=os.getpid(),  # our own PID is never a postmaster
            process_command=owned_command,
            status_output=f"pg_ctl: server is running (PID: {os.getpid()})",
        )


# ---------------------------------------------------------------------------
# Cluster/connection construction (no server started)
# ---------------------------------------------------------------------------
def test_initdb_command_forbids_tcp_and_requires_private_socket(tmp_path):
    _, root = _prepared_root(tmp_path)
    argv = harness.build_initdb_argv(
        "/usr/local/bin", root / "data", "atom_accept_role")
    assert argv[0] == "/usr/local/bin/initdb"
    assert argv[1:3] == ["-D", str(root / "data")]
    assert argv[3:5] == ["-U", "atom_accept_role"]
    assert "--auth-local=trust" in argv
    assert "--auth-host=reject" in argv
    assert "--auth=trust" not in argv

    config = harness.render_cluster_config(root / "sock", 24680)
    assert "listen_addresses = ''" in config
    assert f"unix_socket_directories = '{root / 'sock'}'" in config
    assert "unix_socket_permissions = 0700" in config
    assert "port = 24680" in config
    assert "bonjour = off" in config
    assert "5432" not in config and "5433" not in config


def test_port_choice_never_returns_shared_ports():
    chooser = random.Random(20261117)
    for _ in range(200):
        port = harness.choose_port(rng=chooser)
        assert 20000 <= port <= 60000
        assert port not in harness.SHARED_PORTS
    for shared in (5432, 5433, 8181, 8082):
        with pytest.raises(harness.SafetyRefusal):
            harness.assert_safe_port(shared)


def test_database_url_is_socket_only_and_refuses_tcp(tmp_path):
    _, root = _prepared_root(tmp_path)
    marker = _marker(root)
    url = harness.build_database_url(marker)
    target = harness.assert_socket_only_url(url, marker)
    assert target["socket_directory"] == str(root / "sock")
    assert target["port"] == marker["port"]
    assert url.host is None and url.port is None

    tcp_url = url.set(query={**url.query, "host": "localhost"})
    with pytest.raises(harness.SafetyRefusal):
        harness.assert_socket_only_url(tcp_url, marker)

    shared_port_url = url.set(
        query={**url.query, "port": str(5432)})
    with pytest.raises(harness.SafetyRefusal):
        harness.assert_socket_only_url(shared_port_url, marker)

    wrong_socket = url.set(
        query={**url.query, "host": str(root.parent / "other" / "sock")})
    with pytest.raises(harness.SafetyRefusal):
        harness.assert_socket_only_url(wrong_socket, marker)


def test_child_environment_sets_import_guards_before_backend(tmp_path):
    _, root = _prepared_root(tmp_path)
    marker = _marker(root)
    url = str(harness.build_database_url(marker))
    environment = harness.sanitized_environment(
        root, Path("/usr/local/bin"), url)
    assert environment["TESTING"] == "1"
    assert environment["PYTHON_DOTENV_DISABLED"] == "1"
    assert environment["SECRET_KEY"].startswith("atom-postgres-lineage")
    assert environment["DATABASE_URL"] == url
    assert "host=%2F" in url or str(root / "sock").replace("/", "%2F") in url
    assert environment["HOME"] == str(root / "home")
    assert environment["TMPDIR"] == str(root / "tmp")
    for forbidden in ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGSERVICE"):
        assert forbidden not in environment


# ---------------------------------------------------------------------------
# libpq isolation (SQLAlchemy/psycopg2 runs in the parent process)
# ---------------------------------------------------------------------------
def test_isolated_libpq_environment_removes_owner_inputs_without_mutation(
    tmp_path,
):
    _, root = _prepared_root(tmp_path)
    hostile = {
        "PATH": "/usr/bin:/bin",
        "LANG": "C",
        "HOME": str(root.parent / "owner-home"),
        "TMPDIR": str(root.parent / "owner-tmp"),
        "DATABASE_URL": (
            "postgresql://owner@/owner_db"
            "?host=/private/tmp/atom-pg-owner-socket-never-used"),
        "PGSERVICE": "owner_service",
        "PGSERVICEFILE": str(root.parent / "owner-home/.pg_service.conf"),
        "PGPASSFILE": str(root.parent / "owner-home/.pgpass"),
        "PGPASSWORD": "synthetic-not-a-credential",
        "PGHOST": str(root.parent / "owner-sock"),
        "PGHOSTADDR": "127.0.0.1",
        "PGPORT": "5432",
        "PGDATABASE": "owner_db",
        "PGUSER": "owner_user",
        "PGSSLMODE": "require",
        "PGSSLROOTCERT": str(root.parent / "owner-home/root.crt"),
        "PGSSLCERT": str(root.parent / "owner-home/postgresql.crt"),
        "PGSSLKEY": str(root.parent / "owner-home/postgresql.key"),
        "PGSSLCRL": str(root.parent / "owner-home/root.crl"),
        "PGSSLCRLDIR": str(root.parent / "owner-home/crls"),
        "PGOPTIONS": "-c statement_timeout=1",
        "PGCHANNELBINDING": "require",
        "PGGSSENCMODE": "require",
    }
    snapshot = dict(hostile)

    clean = harness.isolated_libpq_environment(hostile, root=root)

    assert hostile == snapshot, "the input environment must not be mutated"
    for key in snapshot:
        if key.upper().startswith("PG") or key == "DATABASE_URL":
            assert key not in clean
    assert clean["HOME"] == str(root / "home")
    assert clean["TMPDIR"] == str(root / "tmp")
    assert clean["TESTING"] == "1"
    assert clean["PYTHON_DOTENV_DISABLED"] == "1"
    assert clean["PATH"] == hostile["PATH"]
    assert clean["LANG"] == "C"
    assert clean[harness.LIBPQ_ISOLATION_MARKER] == "1"
    removed = set(clean[harness.LIBPQ_REMOVED_ENV].split(","))
    assert {"PGSERVICE", "PGSERVICEFILE", "PGPASSFILE", "PGPASSWORD",
            "PGSSLMODE", "PGSSLROOTCERT", "DATABASE_URL"} <= removed
    assert harness.libpq_environment_is_isolated(clean, root=root) is True
    assert harness.libpq_environment_is_isolated(hostile, root=root) is False


def test_libpq_connect_options_pin_private_paths_and_disable_fallbacks(
    tmp_path,
):
    _, root = _prepared_root(tmp_path)
    options = harness.libpq_isolation_options(root)

    assert options["passfile"] == str(root / "libpq" / "pgpass")
    assert Path(options["passfile"]).parent.parent == root
    assert options["sslmode"] == "disable"
    assert options["gssencmode"] == "disable"
    assert options["channel_binding"] == "disable"
    assert options["hostaddr"] == ""
    assert options["options"] == ""
    assert options["target_session_attrs"] == "any"
    assert options["client_encoding"] == "UTF8"
    assert options["application_name"] == harness.APP_NAME
    # host/port/user/dbname come from the socket-only URL; service must be
    # absent (an explicit empty service is a real service-file lookup).
    for key in ("host", "port", "user", "dbname", "service", "password",
                "sslrootcert", "sslcert", "sslkey", "sslcrl", "sslcrldir"):
        assert key not in options
    assert not (root / "libpq").exists()
    assert harness.libpq_connect_args(root) == options


def test_prepare_fails_closed_without_cli_libpq_isolation(tmp_path, monkeypatch):
    allowed = _real_tmp_root(tmp_path)
    root = allowed / "would-be-cluster"
    monkeypatch.setenv("PGSERVICE", "owner_service")
    instance = harness.AcceptanceHarness(str(root))
    with pytest.raises(harness.SafetyRefusal):
        instance.prepare()
    assert not root.exists()


def test_cleanup_without_a_prepared_cluster_does_nothing():
    instance = harness.AcceptanceHarness(None)
    assert instance.cleanup() is True
    assert instance.report["cleanup"]["stopped"] is True


def test_cleanup_without_marker_refuses_process_actions(tmp_path):
    allowed = _real_tmp_root(tmp_path)
    root = harness.create_scratch_layout(
        allowed / "markerless", allowed_root=allowed)
    instance = harness.AcceptanceHarness(str(root))
    instance.root = root
    instance.marker = None
    assert instance.cleanup() is True
    assert instance.report["cleanup"]["stopped"] is False
    assert "no ownership marker" in instance.report["cleanup"]["reason"]
    assert not (root / "data").exists()


# ---------------------------------------------------------------------------
# Migration source contract (still no database)
# ---------------------------------------------------------------------------
def test_migration_revision_and_constants_match_the_acceptance():
    migration = harness.load_migration()
    assert migration.revision == "20261117_dataset_entry_lineage"
    assert migration.down_revision == "20261116_action_autonomy_rules"
    assert migration.TABLE == "dataset_entries"
    assert migration.COLUMN == "source_document_id"
    assert migration.INDEX == "ix_dataset_entries_source_document_id"
    assert len(migration.revision) <= 32
    assert len(migration.down_revision) <= 32


def test_migration_is_additive_and_never_backfills():
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "op.add_column(" in source
    assert "op.create_index(" in source
    assert "batch_alter_table" in source
    for forbidden in (
        "op.execute(",
        "UPDATE ",
        "INSERT INTO",
        "DELETE FROM",
        "op.create_table(",
        "op.drop_table(",
        "postgresql://",
        "localhost:5433",
    ):
        assert forbidden not in source


def test_acceptance_and_migration_target_the_same_migration_file():
    migration = harness.load_migration()
    assert Path(migration.__file__).resolve() == MIGRATION_PATH.resolve()


# ---------------------------------------------------------------------------
# Necessary real contract: opt-in only
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    os.environ.get("ATOM_PG_LINEAGE_ACCEPTANCE_REAL") != "1",
    reason=(
        "real PostgreSQL acceptance is opt-in; run with "
        "ATOM_PG_LINEAGE_ACCEPTANCE_REAL=1"
    ),
)
def test_real_scratch_cluster_upgrade_contract():
    """Invoke the public harness once and validate its observable report."""
    root = (
        Path("/private/tmp")
        / f"atom-pg-lineage-pytest-{uuid.uuid4().hex[:10]}"
    )
    # Simulated owner files, all unreadable (mode 000), plus hostile inherited
    # libpq values. They live beside the cluster root, never in the repo or the
    # real owner's home. If the harness consulted any of them the run would
    # fail, so success plus the resolved libpq parameters is the evidence.
    owner_home = root.parent / f"{root.name}-owner-home"
    owner_home.mkdir(mode=0o700)
    owner_service = owner_home / ".pg_service.conf"
    owner_service.write_text(
        "[owner_service]\nhost=/owner/socket\npassword=synthetic-not-a-credential\n",
        encoding="utf-8",
    )
    owner_passfile = owner_home / ".pgpass"
    owner_passfile.write_text(
        "*:*:*:owner_user:synthetic-not-a-credential\n", encoding="utf-8")
    owner_root_cert = owner_home / "root.crt"
    owner_root_cert.write_text("not a certificate\n", encoding="utf-8")
    for path in (owner_service, owner_passfile, owner_root_cert):
        os.chmod(path, 0o000)

    command = [
        sys.executable,
        str(HARNESS_PATH),
        "--scratch-root",
        str(root),
    ]
    environment = os.environ.copy()
    environment.update({
        "PYTHON_DOTENV_DISABLED": "1",
        "TESTING": "1",
        "SECRET_KEY": "atom-postgres-lineage-pytest-synthetic",
        "HOME": str(owner_home),
        "DATABASE_URL": (
            "postgresql://owner@/owner_db"
            "?host=/private/tmp/atom-pg-owner-socket-never-used"),
        "PGSERVICE": "owner_service",
        "PGSERVICEFILE": str(owner_service),
        "PGPASSFILE": str(owner_passfile),
        "PGPASSWORD": "synthetic-not-a-credential",
        "PGHOST": str(owner_home / "socket"),
        "PGHOSTADDR": "127.0.0.1",
        "PGPORT": "5432",
        "PGDATABASE": "owner_db",
        "PGUSER": "owner_user",
        "PGSSLMODE": "require",
        "PGSSLROOTCERT": str(owner_root_cert),
        "PGSSLCERT": str(owner_home / "postgresql.crt"),
        "PGSSLKEY": str(owner_home / "postgresql.key"),
        "PGOPTIONS": "-c statement_timeout=1",
        "PGCHANNELBINDING": "require",
        "PGGSSENCMODE": "require",
    })
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        env=environment,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert completed.returncode == 0, (
        f"harness failed\nstdout:\n{completed.stdout[-4000:]}\n"
        f"stderr:\n{completed.stderr[-4000:]}"
    )
    report = json.loads((root / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert report["checks_all_passed"] is True
    assert all(report["checks"].values())
    assert report["server"]["listen_addresses"] == ""
    assert report["server"]["tcp_listen_ports"] == []
    assert report["server"]["data_directory"] == str(root / "data")

    isolation = report["libpq_isolation"]
    removed = set(isolation["inherited_pg_environment_variables_removed"])
    assert {"PGSERVICE", "PGSERVICEFILE", "PGPASSFILE", "PGPASSWORD",
            "PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGSSLMODE",
            "PGSSLROOTCERT", "PGOPTIONS", "PGCHANNELBINDING",
            "PGGSSENCMODE", "DATABASE_URL"} <= removed
    assert "owner_home" not in report["environment_keys"]
    resolved = isolation["resolved"]
    assert resolved["host"] == str(root / "sock")
    assert resolved["port"] == str(report["server"]["port"])
    assert resolved["user"] == report["server"]["current_user"]
    assert resolved["dbname"] == report["server"]["current_database"]
    assert resolved["passfile"] == str(root / "libpq" / "pgpass")
    assert resolved["sslmode"] == "disable"
    assert resolved["gssencmode"] == "disable"
    assert resolved["channel_binding"] == "disable"
    assert resolved["application_name"] == "atom-document-lineage-acceptance"
    assert resolved.get("service") in (None, "")
    assert resolved.get("sslrootcert") in (None, "")
    assert resolved.get("sslcert") in (None, "")
    assert resolved.get("sslkey") in (None, "")
    assert resolved.get("hostaddr") in (None, "")
    assert resolved.get("options") in (None, "")
    for path in (owner_service, owner_passfile, owner_root_cert):
        assert stat.S_IMODE(path.stat().st_mode) == 0o000

    assert report["restart"]["old_pid"] != report["restart"]["new_pid"]
    assert report["after"]["lineage_values"]["seed-active"] == (
        "doc-acceptance-upgrade-2")
    assert report["after"]["unique_constraints"] == {
        "uq_dataset_entries_version": [
            "source_kind", "source", "external_id", "content_hash",
            "entity_name",
        ],
    }
    assert len(report["proof_digest"]) == 64
    assert report["cleanup"]["stopped"] is True
    assert report["cleanup"]["recursive_delete_performed"] is False
    assert (root / "data").is_dir()
    assert (root / "report.json").is_file()
