"""Focused disposable regression for ``release_tool.py rollback`` (WO-OPS-04).

Every release root, release tree, SQLite file and receipt lives under pytest's
``tmp_path``.  The real ``cmd_rollback`` target validation, active-pointer flip
and receipt publication run unchanged.  Only ``start_release_services`` (the
service-launch + ``/api/health`` leaf) is replaced with a controlled double,
so no uvicorn/node process, port, live path, credential or live database is
touched.  Network and process control are denied by the autouse guard.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))
import release_identity  # noqa: E402
import release_tool  # noqa: E402


@pytest.fixture(autouse=True)
def _deny_network_and_process_control(monkeypatch):
    def deny(*_args, **_kwargs):
        raise AssertionError(
            "rollback regression must not use network or process control")

    monkeypatch.setattr(release_tool, "http_json", deny)
    monkeypatch.setattr(release_tool, "wait_health", deny)
    monkeypatch.setattr(release_tool, "stop_pid", deny)
    monkeypatch.setattr(release_tool, "cmd_start", deny)
    monkeypatch.setattr(release_tool, "listener_pids", lambda _port: [])


def _identity(*, release_commit: str, release_tag: str, tree: str) -> dict:
    return {
        "schema": "atom-assignment-successor-release-1",
        "release_tag": release_tag,
        "release_commit": release_commit,
        "tested_runtime_commit": release_identity.TESTED_RUNTIME_COMMIT,
        "product_paths": ["backend", "frontend-nextjs"],
        "product_tree_sha256": tree,
        "frontend_build_id": "test-build",
        "api_port": 18071,
        "frontend_port": 13130,
        "audience": "single_user",
        "pilot_email": "admin@example.invalid",
        "outbound_scope": "draft_and_approval_only",
        "send_authorized": False,
        "topology": "one_worker_process_per_assignment",
    }


def _candidate_identity(**overrides) -> dict:
    identity = _identity(
        release_commit=release_identity.RELEASE_COMMIT,
        release_tag=release_identity.RELEASE_TAG,
        tree=release_identity.EXPECTED_PRODUCT_TREE_SHA256,
    )
    identity.update(overrides)
    return identity


def _rollback_identity(**overrides) -> dict:
    identity = _identity(
        release_commit=release_identity.ROLLBACK_COMMIT,
        release_tag=release_identity.ROLLBACK_TAG,
        tree=release_identity.ROLLBACK_PRODUCT_TREE_SHA256,
    )
    identity.update(overrides)
    return identity


def _make_release(root: Path, name: str, identity: dict, *, backend: bool = True,
                  frontend: bool = True) -> Path:
    release = root / "releases" / name
    (release / "app").mkdir(parents=True)
    if backend:
        (release / "app" / "backend").mkdir()
    if frontend:
        (release / "frontend").mkdir()
        (release / "frontend" / "server.js").write_text(
            "// controlled frontend leaf\n")
    (release / "RELEASE_IDENTITY.json").write_text(
        json.dumps(identity, indent=2) + "\n")
    return release


def _make_root(tmp_path: Path, *, previous_identity: dict | None = None,
               previous: bool = True, backend: bool = True,
               frontend: bool = True) -> dict:
    root = tmp_path / "release-root"
    (root / "config").mkdir(parents=True)
    (root / "run").mkdir()
    (root / "logs").mkdir()
    data = root / "data"
    data.mkdir()
    db = data / "atom.db"
    con = sqlite3.connect(db)
    try:
        con.execute("CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT)")
        con.execute(
            "INSERT INTO users VALUES ('user-1', 'user@example.invalid')")
        con.commit()
    finally:
        con.close()
    (root / "config" / "env.release").write_text(
        "API_PORT=18071\n"
        "FE_PORT=13130\n"
        f"ATOM_DATA_DIR={data}\n"
        f"ATOM_OFFICE_DIR={data / 'office'}\n")

    candidate_identity = _candidate_identity()
    candidate = _make_release(root, "candidate", candidate_identity)
    (root / "current").symlink_to(candidate)
    (root / "RELEASE_IDENTITY.json").write_text(
        json.dumps(candidate_identity, indent=2) + "\n")

    rollback = None
    rollback_identity = previous_identity or _rollback_identity()
    if previous:
        rollback = _make_release(
            root, "rollback", rollback_identity, backend=backend,
            frontend=frontend)
        (root / "previous").symlink_to(rollback)

    return {
        "root": root,
        "data": data,
        "db": db,
        "db_sha256": hashlib.sha256(db.read_bytes()).hexdigest(),
        "candidate": candidate,
        "candidate_identity": candidate_identity,
        "rollback": rollback,
        "rollback_identity": rollback_identity,
    }


def _snapshot(world: dict) -> dict:
    root = world["root"]

    def link(name: str) -> str | None:
        path = root / name
        return os.readlink(path) if path.is_symlink() else None

    return {
        "current": link("current"),
        "previous": link("previous"),
        "root_identity": (root / "RELEASE_IDENTITY.json").read_bytes(),
        "db_sha256": hashlib.sha256(world["db"].read_bytes()).hexdigest(),
        "run": sorted(path.name for path in (root / "run").iterdir()),
        "logs": sorted(path.name for path in (root / "logs").iterdir()),
    }


def _rollback(world: dict) -> int:
    return release_tool.cmd_rollback(SimpleNamespace(root=str(world["root"])))


def _controlled_start(world: dict, calls: list[dict], *, ok: bool = True):
    """Stand-in for the service-launch + health leaf; never starts a process."""

    def start(root, release, identity, env, *, mode):
        assert root == world["root"]
        assert release == world["rollback"]
        assert identity == world["rollback_identity"]
        assert mode == "rollback"
        assert env["ATOM_DATA_DIR"] == str(world["data"])
        # The active pointer must already be flipped before the service leaf is
        # asked to start, and shutdown must have completed first.
        assert (root / "current").resolve() == world["rollback"].resolve()
        assert (root / "previous").resolve() == world["candidate"].resolve()
        assert (root / "run" / "stop_receipt.json").is_file()
        assert hashlib.sha256(world["db"].read_bytes()).hexdigest() == (
            world["db_sha256"])
        calls.append({"release": release, "mode": mode,
                      "data_dir": env["ATOM_DATA_DIR"]})
        if not ok:
            return False, {"error": "controlled health leaf failure"}
        return True, {
            "schema": "atom-assignment-release-startup-1",
            "mode": mode,
            "release_commit": identity["release_commit"],
            "release_tag": identity.get("release_tag"),
            "health_identity": {
                "revision": identity["release_commit"],
                "dirty": False,
            },
            "health_status": "healthy",
            "backend_pid": 4242,
            "frontend_pid": 4243,
        }

    return start


def test_rollback_success_flips_pointer_preserves_db_and_writes_receipt(
        tmp_path, monkeypatch):
    world = _make_root(tmp_path)
    before = _snapshot(world)
    calls: list[dict] = []
    monkeypatch.setattr(
        release_tool, "start_release_services", _controlled_start(world, calls))

    assert _rollback(world) == 0

    assert calls == [{
        "release": world["rollback"],
        "mode": "rollback",
        "data_dir": str(world["data"]),
    }]
    assert (world["root"] / "current").resolve() == world["rollback"].resolve()
    assert (world["root"] / "previous").resolve() == world["candidate"].resolve()
    assert json.loads(
        (world["root"] / "RELEASE_IDENTITY.json").read_text()
    ) == world["rollback_identity"]

    receipt = json.loads(
        (world["root"] / "run" / "rollback_receipt.json").read_text())
    assert receipt["schema"] == "atom-assignment-release-rollback-1"
    assert Path(receipt["from_release"]) == world["candidate"].resolve()
    assert Path(receipt["to_release"]) == world["rollback"].resolve()
    assert receipt["to_release_commit"] == release_identity.ROLLBACK_COMMIT
    assert receipt["start_ok"] is True
    assert receipt["startup"]["health_status"] == "healthy"
    assert receipt["health_identity"] == {
        "revision": release_identity.ROLLBACK_COMMIT, "dirty": False}
    assert receipt["database_restored"] is False
    assert receipt["user_data_preserved"] is True
    assert receipt["data_dir"] == str(world["data"])
    assert receipt["new_interactive_approval_required"] is False

    # Rollback is a code-pointer operation: user DB bytes are untouched.
    assert hashlib.sha256(world["db"].read_bytes()).hexdigest() == (
        before["db_sha256"])

    stop = json.loads(
        (world["root"] / "run" / "stop_receipt.json").read_text())
    assert stop["schema"] == "atom-assignment-release-stop-1"
    assert stop["results"] == [
        {"label": "backend", "stopped": True, "detail": "no_pidfile"},
        {"label": "frontend", "stopped": True, "detail": "no_pidfile"},
    ]
    assert stop["reaped_release_listeners"] == []
    assert not (world["root"] / "run" / "backend.pid").exists()
    assert not (world["root"] / "run" / "frontend.pid").exists()


def test_rollback_start_failure_is_receipted_without_touching_db(
        tmp_path, monkeypatch):
    world = _make_root(tmp_path)
    before = _snapshot(world)
    calls: list[dict] = []
    monkeypatch.setattr(
        release_tool, "start_release_services",
        _controlled_start(world, calls, ok=False))

    assert _rollback(world) == 1

    assert len(calls) == 1
    assert (world["root"] / "current").resolve() == world["rollback"].resolve()
    assert (world["root"] / "previous").resolve() == world["candidate"].resolve()
    receipt = json.loads(
        (world["root"] / "run" / "rollback_receipt.json").read_text())
    assert receipt["start_ok"] is False
    assert receipt["startup"] == {"error": "controlled health leaf failure"}
    assert receipt["health_identity"] is None
    assert receipt["database_restored"] is False
    assert receipt["user_data_preserved"] is True
    assert hashlib.sha256(world["db"].read_bytes()).hexdigest() == (
        before["db_sha256"])


def _assert_refused_before_effects(world: dict, before: dict,
                                   monkeypatch, expected: str) -> None:
    def forbidden_start(*_args, **_kwargs):
        raise AssertionError(
            "start_release_services must not run before target validation")

    monkeypatch.setattr(release_tool, "start_release_services", forbidden_start)
    with pytest.raises(SystemExit) as exc:
        _rollback(world)
    assert expected in str(exc.value)
    assert _snapshot(world) == before


def test_rollback_refuses_missing_previous_link_before_effects(
        tmp_path, monkeypatch):
    world = _make_root(tmp_path, previous=False)
    before = _snapshot(world)
    _assert_refused_before_effects(
        world, before, monkeypatch, "no previous release link")


def test_rollback_refuses_wrong_target_commit_before_effects(
        tmp_path, monkeypatch):
    world = _make_root(
        tmp_path,
        previous_identity=_rollback_identity(release_commit="0" * 40))
    before = _snapshot(world)
    _assert_refused_before_effects(
        world, before, monkeypatch, "is not the expected rollback")


def test_rollback_refuses_wrong_target_tree_before_effects(
        tmp_path, monkeypatch):
    # Rollback commit paired with the candidate tree: the commit is allowed but
    # the identity does not describe the tree that commit actually produced.
    world = _make_root(
        tmp_path,
        previous_identity=_rollback_identity(
            product_tree_sha256=release_identity.EXPECTED_PRODUCT_TREE_SHA256))
    before = _snapshot(world)
    _assert_refused_before_effects(
        world, before, monkeypatch,
        "product tree does not match its commit")


@pytest.mark.parametrize(
    ("backend", "frontend"),
    [
        (False, True),
        (True, False),
        (False, False),
    ],
)
def test_rollback_refuses_incomplete_target_before_effects(
        tmp_path, monkeypatch, backend, frontend):
    world = _make_root(tmp_path, backend=backend, frontend=frontend)
    before = _snapshot(world)
    _assert_refused_before_effects(
        world, before, monkeypatch, "rollback target release is incomplete")
