"""Whole-file controls for the launcher's storage preflight.

The bug these pin
-----------------
``scripts/acceptance/launch_integrated_local_candidate.sh`` validated a world
through ``validate_local_world.py`` (which honoured
``ATOM_WORLD_STORAGE_PATHS``), then independently parsed the CHECKOUT
``backend/config/world_storage.json`` and ``mkdir -p``'d its local worlds root
BEFORE ``core.world_storage_guard`` ran. With a relocated store declared, that
created the checkout's canonical ``backend/data/acceptance_worlds`` even when
the guard then correctly refused the relocated layout.

What is exercised here
----------------------
* the REAL shell launcher, the REAL ``core.world_storage_guard`` and the REAL
  ``validate_local_world.py`` against absolute ``tmp_path`` fixtures;
* the documented explicit store provisioner added by this repair;
* a labelled pre-server boundary: the test ``PYTHON`` shim delegates every
  normal invocation to the real interpreter and only records + exits before
  ``uvicorn``. No server, browser, provider, model, live DB or canonical world
  is started or written.

Everything runs in ``tmp_path``; the only checkout files read are the launcher,
validator, provisioner and the tracked storage config (which is hashed to
prove it was not rewritten).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import socket
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
from scripts.orchestration_acceptance import storage_policy as SP  # noqa: E402

LAUNCHER = REPO / "scripts" / "acceptance" / "launch_integrated_local_candidate.sh"
VALIDATOR = REPO / "scripts" / "acceptance" / "validate_local_world.py"
PROVISIONER = REPO / "scripts" / "acceptance" / "provision_isolated_world_store.py"
CANVAS = REPO / "scripts" / "acceptance" / "canvas_blank_lifecycle.py"
CHECKOUT_CONFIG = BACKEND / "config" / "world_storage.json"
CANONICAL_ROOT = BACKEND / "data" / "acceptance_worlds"

_VALIDATOR_MODULE = None


# ---------------------------------------------------------------------------
# fixtures and helpers
# ---------------------------------------------------------------------------
def _validator_module():
    global _VALIDATOR_MODULE
    if _VALIDATOR_MODULE is None:
        spec = importlib.util.spec_from_file_location(
            "validate_local_world", VALIDATOR)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _VALIDATOR_MODULE = module
    return _VALIDATOR_MODULE


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _free_ports() -> tuple[int, int]:
    socks = []
    ports = []
    try:
        for _ in range(2):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", 0))
            socks.append(sock)
            ports.append(sock.getsockname()[1])
    finally:
        for sock in socks:
            sock.close()
    assert ports[0] != ports[1]
    return ports[0], ports[1]


def _write_config(config_dir: Path, *, root: Path, top_layout: str = "local",
                  worlds_layout: str | None = None,
                  volume: dict | None = None, enabled: bool = True) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    worlds: dict = {"root": str(root)}
    if worlds_layout is not None:
        worlds["layout"] = worlds_layout
    payload: dict = {
        "enabled": enabled,
        "layout": top_layout,
        "worlds": worlds,
        "symlink_sample": 0,
        "fail_on_broken_symlinks": False,
    }
    if volume is not None:
        payload["volume"] = volume
    path = config_dir / "world_storage.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _space_driver(tmp_path: Path) -> Path:
    """A read-only storage-policy CLI driver with an injected diskstat map.

    The production module and its CLI are used unchanged; only
    ``real_free_bytes`` is replaced (the documented test seam for exhaustion),
    keyed by the actual probe path. No guard verdict or world is faked.
    """
    path = tmp_path / "space-driver.py"
    path.write_text(
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, os.environ['ATOM_TEST_BACKEND'])\n"
        "import scripts.orchestration_acceptance.storage_policy as SP\n"
        "mapping = json.loads(os.environ['ATOM_TEST_FREE_MAP'])\n"
        "def fake(path):\n"
        "    actual = str(Path(path).resolve(strict=False))\n"
        "    for key, value in sorted(mapping.items(), key=lambda kv: -len(kv[0])):\n"
        "        key = str(Path(key).resolve(strict=False))\n"
        "        if actual == key or actual.startswith(key.rstrip('/') + '/'):\n"
        "            return int(value)\n"
        "    return 50 * 1024 ** 3\n"
        "SP.real_free_bytes = fake\n"
        "raise SystemExit(SP.main(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    return path


def _shim(tmp_path: Path) -> Path:
    """A PYTHON that delegates normally, records/stops at the uvicorn boundary.

    ``ATOM_TEST_REMOVE_ROOT_AFTER_GUARD`` makes the shim remove an empty root
    on the ``capture_runtime_identity`` call, simulating the root vanishing
    between the full preflight and the world mkdir. The launcher must refuse
    rather than let ``mkdir -p`` recreate it. ``ATOM_TEST_SPACE_DRIVER`` routes
    only the storage-policy CLI through the injected-diskstat driver above.
    """
    path = tmp_path / "python-shim"
    path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ \"${1:-}\" == \"-m\" && \"${2:-}\" == \"uvicorn\" ]]; then\n"
        "  printf '%s\\n' \"$*\" > \"${ATOM_TEST_SERVER_BOUNDARY:?}\"\n"
        "  exit 97\n"
        "fi\n"
        "if [[ \"${1:-}\" == \"-m\" && "
        "\"${2:-}\" == \"scripts.orchestration_acceptance.storage_policy\" && "
        "-n \"${ATOM_TEST_SPACE_DRIVER:-}\" ]]; then\n"
        "  shift 2\n"
        "  exec \"${ATOM_TEST_REAL_PYTHON:?}\" \"${ATOM_TEST_SPACE_DRIVER}\" \"$@\"\n"
        "fi\n"
        "if [[ -n \"${ATOM_TEST_REMOVE_ROOT_AFTER_GUARD:-}\" && "
        "\"$*\" == *capture_runtime_identity* ]]; then\n"
        "  rm -rf -- \"${ATOM_TEST_REMOVE_ROOT_AFTER_GUARD}\"\n"
        "fi\n"
        "exec \"${ATOM_TEST_REAL_PYTHON:?}\" \"$@\"\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _base_env(tmp_path: Path, *, world: Path, boundary: Path,
              config_dir: Path | None = None,
              remove_root_after_guard: Path | None = None,
              extra_path: Path | None = None,
              space_driver: Path | None = None,
              free_map: dict | None = None) -> dict:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    tmp = tmp_path / "tmp"
    tmp.mkdir(exist_ok=True)
    frontend = tmp_path / "frontend"
    (frontend / ".next").mkdir(parents=True, exist_ok=True)
    (frontend / ".next" / "BUILD_ID").write_text("test-build\n", encoding="utf-8")
    backend_port, frontend_port = _free_ports()

    env = os.environ.copy()
    for name in (
        "ATOM_WORLD_STORAGE_PATHS", "ATOM_WORLD_STORAGE_BYPASS",
        "ATOM_FRONTEND_DIR", "WORLD", "ADMIN_PASSWORD",
        "ATOM_TEST_SERVER_BOUNDARY", "ATOM_TEST_REMOVE_ROOT_AFTER_GUARD",
        "ATOM_TEST_REAL_PYTHON", "ATOM_TEST_BACKEND", "ATOM_TEST_SPACE_DRIVER",
        "ATOM_TEST_FREE_MAP", "FAKE_DISKUTIL_NAME", "FAKE_DISKUTIL_UUID",
    ):
        env.pop(name, None)
    env.update({
        "TESTING": "1",
        "PYTHON_DOTENV_DISABLED": "1",
        "HOME": str(home),
        "TMPDIR": str(tmp),
        "ATOM_DB_SNAPSHOT_MIN_FREE_MB": "0",
        "DATABASE_URL": f"sqlite:///{tmp}/scratch.db",
        "ADMIN_PASSWORD": "launcher-storage-preflight-test-password",
        "PYTHON": str(_shim(tmp_path)),
        "ATOM_TEST_REAL_PYTHON": sys.executable,
        "ATOM_TEST_BACKEND": str(BACKEND),
        "ATOM_TEST_SERVER_BOUNDARY": str(boundary),
        "ATOM_FRONTEND_DIR": str(frontend),
        "WORLD": str(world),
        "BACKEND_PORT": str(backend_port),
        "FRONTEND_PORT": str(frontend_port),
        "MIN_FREE_MB": "1",
    })
    if config_dir is not None:
        env["ATOM_WORLD_STORAGE_PATHS"] = str(config_dir)
    if remove_root_after_guard is not None:
        env["ATOM_TEST_REMOVE_ROOT_AFTER_GUARD"] = str(remove_root_after_guard)
    if space_driver is not None:
        env["ATOM_TEST_SPACE_DRIVER"] = str(space_driver)
    if free_map is not None:
        env["ATOM_TEST_FREE_MAP"] = json.dumps(
            {str(key): int(value) for key, value in free_map.items()})
    if extra_path is not None:
        env["PATH"] = f"{extra_path}{os.pathsep}{env.get('PATH', '')}"
    return env


def _run_launcher(env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(LAUNCHER)], cwd=REPO, env=env,
        capture_output=True, text=True, timeout=240,
    )


def _run_validator(env: dict, world: Path) -> subprocess.CompletedProcess:
    """Run the real validator with its own free ports (no launcher)."""
    backend_port, frontend_port = _free_ports()
    args = [
        sys.executable, str(VALIDATOR), "--world", str(world),
        "--repo", str(REPO), "--backend-port", str(backend_port),
        "--frontend-port", str(frontend_port), "--min-free-mb", "1",
    ]
    return subprocess.run(
        args, cwd=REPO, env=env, capture_output=True, text=True, timeout=120)


def _run_provisioner(base: Path, name: str = "isolated-worlds",
                     config_dir: Path | None = None,
                     env: dict | None = None) -> subprocess.CompletedProcess:
    args = [sys.executable, str(PROVISIONER), "--base", str(base), "--name", name]
    if config_dir is not None:
        args += ["--config-dir", str(config_dir)]
    run_env = dict(os.environ)
    run_env.update({"TESTING": "1", "PYTHON_DOTENV_DISABLED": "1"})
    run_env.pop("ATOM_WORLD_STORAGE_PATHS", None)
    run_env.pop("ATOM_WORLD_STORAGE_BYPASS", None)
    if env:
        run_env.update(env)
    return subprocess.run(
        args, cwd=REPO, env=run_env, capture_output=True, text=True, timeout=120)


def _space_env(tmp_path: Path, config_dir: Path, free_map: dict) -> dict:
    """Scratch-only env for the storage-policy subprocess (no owner state)."""
    home = tmp_path / "space-home"
    home.mkdir(exist_ok=True)
    tmp = tmp_path / "space-tmp"
    tmp.mkdir(exist_ok=True)
    env = os.environ.copy()
    for name in ("ATOM_WORLD_STORAGE_BYPASS",
                 "ATOM_WORLD_STORAGE_PATHS"):
        env.pop(name, None)
    env.update({
        "TESTING": "1",
        "PYTHON_DOTENV_DISABLED": "1",
        "HOME": str(home),
        "TMPDIR": str(tmp),
        "DATABASE_URL": f"sqlite:///{tmp}/space-scratch.db",
        "ATOM_DB_SNAPSHOT_MIN_FREE_MB": "0",
        "ATOM_WORLD_STORAGE_PATHS": str(config_dir),
        "ATOM_TEST_BACKEND": str(BACKEND),
        "ATOM_TEST_FREE_MAP": json.dumps(
            {str(key): int(value) for key, value in free_map.items()}),
    })
    return env


def _run_space_cli(tmp_path: Path, config_dir: Path, world: Path,
                   free_map: dict) -> subprocess.CompletedProcess:
    """The real storage-policy ``space`` CLI with only diskstat injected."""
    driver = _space_driver(tmp_path)
    env = _space_env(tmp_path, config_dir, free_map)
    return subprocess.run(
        [sys.executable, str(driver), "space", "--world", str(world),
         "--no-build-cache", "--no-run-data", "--json"],
        cwd=BACKEND, env=env, capture_output=True, text=True, timeout=120)


def _assert_no_apps(world: Path, boundary: Path) -> None:
    assert not boundary.exists(), "the uvicorn boundary was reached"
    assert not (world / "backend.pid").exists()
    assert not (world / "frontend.pid").exists()
    assert not world.exists(), f"world was created at {world}"


def _assert_canonical(before: bool) -> None:
    if not before:
        assert not CANONICAL_ROOT.exists(), (
            "the checkout's canonical worlds root was created")


# ---------------------------------------------------------------------------
# static: one authority, no private config parse, guard before write
# ---------------------------------------------------------------------------
def test_launcher_has_no_private_config_parse_or_root_bootstrap():
    src = LAUNCHER.read_text(encoding="utf-8")
    assert "CONFIG=" not in src, (
        "the launcher binds a checkout config path again; it must let "
        "core.world_storage_guard resolve the config (env relocation included)")
    assert "WORLDS_ROOT" not in src
    assert "created configured local worlds root" not in src
    assert 'mkdir -p "$WORLDS_ROOT"' not in src
    guard_check = src.index("core.world_storage_guard check")
    assert_usable = src.index("assert_worlds_root_usable")
    first_world_write = src.index('mkdir -p "$WORLD_REAL/data"')
    assert guard_check < assert_usable < first_world_write, (
        "the full guard and the cheap pre-mkdir root check must both run "
        "before the first world write")


def test_canvas_harness_uses_the_shared_resolver_and_creates_no_root():
    src = CANVAS.read_text(encoding="utf-8")
    assert "CONFIG_PATH" not in src
    assert "worlds_root.mkdir" not in src
    assert "resolve_storage_config" in src
    assert "ensure_storage_guard(python_bin)" in src


# ---------------------------------------------------------------------------
# explicit isolated store provisioning (the documented fresh-world journey)
# ---------------------------------------------------------------------------
def test_provisioned_store_is_guard_valid_and_config_is_outside_the_root(
        tmp_path):
    canonical_before = CANONICAL_ROOT.exists()
    config_hash = _sha256(CHECKOUT_CONFIG)
    base = tmp_path / "run"
    base.mkdir()

    proc = _run_provisioner(base)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    store_root = Path(payload["store_root"])
    config_path = Path(payload["config_path"])

    assert store_root == (base / "isolated-worlds").resolve()
    assert store_root.is_dir()
    assert list(store_root.iterdir()) == []
    assert config_path == (base / "isolated-config" / "world_storage.json")
    assert config_path.is_file()
    assert store_root not in config_path.parents
    assert "world storage preflight OK" in payload["guard_summary"]
    assert payload["canonical_root_created"] is False

    config = json.loads(config_path.read_text())
    assert config["enabled"] is True
    assert config["layout"] == "local"
    assert Path(config["worlds"]["root"]) == store_root

    check = subprocess.run(
        [sys.executable, "-m", "core.world_storage_guard", "check"],
        cwd=BACKEND, env={
            **{k: v for k, v in os.environ.items()
               if k != "ATOM_WORLD_STORAGE_BYPASS"},
            "TESTING": "1",
            "PYTHON_DOTENV_DISABLED": "1",
            "ATOM_WORLD_STORAGE_PATHS": str(config_path.parent),
        }, capture_output=True, text=True, timeout=120,
    )
    assert check.returncode == 0, check.stdout + check.stderr
    assert "world storage preflight OK" in check.stdout

    assert _sha256(CHECKOUT_CONFIG) == config_hash
    _assert_canonical(canonical_before)


def test_provisioning_is_idempotent_for_the_same_empty_store(tmp_path):
    base = tmp_path / "run"
    base.mkdir()
    first = _run_provisioner(base)
    assert first.returncode == 0, first.stderr
    config_path = Path(json.loads(first.stdout)["config_path"])
    before = config_path.read_bytes()

    second = _run_provisioner(base)
    assert second.returncode == 0, second.stderr
    payload = json.loads(second.stdout)
    assert payload["created"] == {
        "store_root": False, "config_dir": False, "config": False}
    assert config_path.read_bytes() == before


def test_provisioning_refuses_a_missing_base_without_creating_it(tmp_path):
    missing = tmp_path / "missing-base"
    proc = _run_provisioner(missing)
    assert proc.returncode == 2
    assert "REFUSED" in proc.stderr
    assert not missing.exists()


def test_provisioning_refuses_config_inside_the_store_root(tmp_path):
    base = tmp_path / "run"
    base.mkdir()
    store_root = base / "isolated-worlds"
    config_dir = store_root / "config"
    proc = _run_provisioner(base, config_dir=config_dir)
    assert proc.returncode == 2
    assert "OUTSIDE" in proc.stderr or "inside the store root" in proc.stderr
    assert not store_root.exists()


def test_provisioning_refuses_an_existing_non_empty_store(tmp_path):
    base = tmp_path / "run"
    store_root = base / "isolated-worlds"
    store_root.mkdir(parents=True)
    sentinel = store_root / "existing-world"
    sentinel.write_text("keep me", encoding="utf-8")
    proc = _run_provisioner(base)
    assert proc.returncode == 2
    assert "not empty" in proc.stderr
    assert sentinel.read_text() == "keep me"
    assert not (base / "isolated-config").exists()


def test_provisioning_refuses_to_overwrite_a_different_config(tmp_path):
    base = tmp_path / "run"
    config_dir = base / "isolated-config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "world_storage.json"
    config_path.write_text('{"enabled": false}\n', encoding="utf-8")
    proc = _run_provisioner(base)
    assert proc.returncode == 2
    assert "different content" in proc.stderr
    assert config_path.read_text() == '{"enabled": false}\n'
    assert not (base / "isolated-worlds").exists()


def test_provisioning_refuses_the_canonical_root_and_bypass(tmp_path):
    canonical_before = CANONICAL_ROOT.exists()
    proc = _run_provisioner(
        CANONICAL_ROOT.parent, name=CANONICAL_ROOT.name)
    assert proc.returncode == 2
    assert "REFUSED" in proc.stderr
    _assert_canonical(canonical_before)

    base = tmp_path / "run"
    base.mkdir()
    proc = _run_provisioner(
        base, env={"ATOM_WORLD_STORAGE_BYPASS": "1"})
    assert proc.returncode == 2
    assert "bypass" in proc.stderr.lower()
    assert not (base / "isolated-worlds").exists()
    assert not (base / "isolated-config").exists()


# ---------------------------------------------------------------------------
# relocated existing store: the world CHILD is created, canonical is not
# ---------------------------------------------------------------------------
def test_relocated_existing_store_creates_only_the_world_child_and_reuses_it(
        tmp_path, monkeypatch):
    canonical_before = CANONICAL_ROOT.exists()
    config_hash = _sha256(CHECKOUT_CONFIG)
    base = tmp_path / "run"
    base.mkdir()
    provision = _run_provisioner(base)
    assert provision.returncode == 0, provision.stderr
    payload = json.loads(provision.stdout)
    store_root = Path(payload["store_root"])
    config_dir = Path(payload["config_path"]).parent
    world = store_root / "fresh-world"
    boundary = tmp_path / "server-boundary"

    env = _base_env(tmp_path, world=world, boundary=boundary,
                    config_dir=config_dir)
    first = _run_launcher(env)
    assert first.returncode == 1, first.stdout + first.stderr
    assert boundary.is_file(), "the labelled pre-server boundary was not reached"
    boundary_text = boundary.read_text()
    assert "-m uvicorn" in boundary_text
    assert "backend exited during startup" in first.stderr
    combined = first.stdout + first.stderr
    assert "world storage preflight OK" in combined
    assert "created configured local worlds root" not in combined

    assert world.is_dir()
    assert (world / "data").is_dir()
    assert (world / "evidence").is_dir()
    marker = json.loads((world / ".atom-integrated-world.json").read_text())
    assert marker["world"] == str(world.resolve())
    assert marker["repo"] == str(REPO)
    assert marker["database"] == str(world / "atom.db")
    secret = world / ".atom-secret"
    assert secret.is_file()
    assert stat.S_IMODE(secret.stat().st_mode) == 0o600
    secret_value = secret.read_text()
    created_at = marker["created_at"]

    # Reuse the same world: no wipe, same secret/created_at, and the sentinel
    # the first journey wrote survives. The stale backend.pid is a launch
    # artifact, not world data; remove it so the test does not depend on PID
    # reuse.
    sentinel = world / "data" / "reuse-sentinel.txt"
    sentinel.write_text("still here", encoding="utf-8")
    (world / "backend.pid").unlink(missing_ok=True)
    boundary.unlink()

    second = _run_launcher(env)
    assert second.returncode == 1, second.stdout + second.stderr
    assert boundary.is_file()
    assert sentinel.read_text() == "still here"
    assert secret.read_text() == secret_value
    assert json.loads((world / ".atom-integrated-world.json").read_text())[
        "created_at"] == created_at

    _assert_canonical(canonical_before)
    assert _sha256(CHECKOUT_CONFIG) == config_hash


# ---------------------------------------------------------------------------
# space policy: the actual target filesystem, both directions
# ---------------------------------------------------------------------------
def test_space_cli_probes_the_relocated_filesystem_in_both_directions(tmp_path):
    base = tmp_path / "run"
    base.mkdir()
    provision = _run_provisioner(base)
    assert provision.returncode == 0, provision.stderr
    payload = json.loads(provision.stdout)
    store_root = Path(payload["store_root"])
    config_dir = Path(payload["config_path"]).parent
    world = store_root / "space-probe-world"
    canonical_before = CANONICAL_ROOT.exists()

    # Canonical ample, relocated insufficient: the OLD canonical probe would
    # have passed while the actual target volume is nearly full.
    low = _run_space_cli(
        tmp_path, config_dir, world,
        {CANONICAL_ROOT: 50 * 1024 ** 3, store_root: 1 * 1024 ** 2})
    assert low.returncode == 1, low.stdout + low.stderr
    low_payload = json.loads(low.stdout)
    assert low_payload["ok"] is False
    assert low_payload["probe_path"] == str(store_root.resolve())
    assert low_payload["probe_source"] == "target_path"
    assert low_payload["free_bytes"] == 1 * 1024 ** 2
    assert "INSUFFICIENT STORAGE" in low_payload["message"]

    # Canonical insufficient, relocated ample: the OLD probe would have
    # refused a perfectly healthy relocated target.
    high = _run_space_cli(
        tmp_path, config_dir, world,
        {CANONICAL_ROOT: 1 * 1024 ** 2, store_root: 50 * 1024 ** 3})
    assert high.returncode == 0, high.stdout + high.stderr
    high_payload = json.loads(high.stdout)
    assert high_payload["ok"] is True
    assert high_payload["probe_path"] == str(store_root.resolve())
    assert high_payload["probe_source"] == "target_path"
    assert high_payload["free_bytes"] == 50 * 1024 ** 3

    assert not world.exists()
    _assert_canonical(canonical_before)


def test_launcher_low_relocated_filesystem_refuses_before_any_write(tmp_path):
    canonical_before = CANONICAL_ROOT.exists()
    base = tmp_path / "run"
    base.mkdir()
    provision = _run_provisioner(base)
    assert provision.returncode == 0, provision.stderr
    payload = json.loads(provision.stdout)
    store_root = Path(payload["store_root"])
    config_dir = Path(payload["config_path"]).parent
    world = store_root / "low-space-world"
    boundary = tmp_path / "server-boundary"

    env = _base_env(
        tmp_path, world=world, boundary=boundary, config_dir=config_dir,
        space_driver=_space_driver(tmp_path),
        free_map={CANONICAL_ROOT: 50 * 1024 ** 3,
                  store_root: 1 * 1024 ** 2})
    proc = _run_launcher(env)
    combined = proc.stdout + proc.stderr
    assert proc.returncode != 0
    assert "INSUFFICIENT STORAGE" in combined
    assert str(store_root.resolve()) in combined
    _assert_no_apps(world, boundary)
    _assert_canonical(canonical_before)


def test_launcher_ample_relocated_filesystem_ignores_low_canonical(tmp_path):
    canonical_before = CANONICAL_ROOT.exists()
    base = tmp_path / "run"
    base.mkdir()
    provision = _run_provisioner(base)
    assert provision.returncode == 0, provision.stderr
    payload = json.loads(provision.stdout)
    store_root = Path(payload["store_root"])
    config_dir = Path(payload["config_path"]).parent
    world = store_root / "ample-relocated-world"
    boundary = tmp_path / "server-boundary"

    env = _base_env(
        tmp_path, world=world, boundary=boundary, config_dir=config_dir,
        space_driver=_space_driver(tmp_path),
        free_map={CANONICAL_ROOT: 1 * 1024 ** 2,
                  store_root: 50 * 1024 ** 3})
    proc = _run_launcher(env)
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 1, combined
    assert boundary.is_file(), "the labelled pre-server boundary was not reached"
    assert "space check OK" in combined
    assert str(store_root.resolve()) in combined
    assert world.is_dir()
    _assert_canonical(canonical_before)


def test_space_cli_missing_relocated_config_refuses_not_canonical(tmp_path):
    base = tmp_path / "run"
    base.mkdir()
    config_dir = base / "missing-config"
    config_dir.mkdir()
    world = CANONICAL_ROOT / "space-would-be-canonical"
    canonical_before = CANONICAL_ROOT.exists()

    proc = _run_space_cli(
        tmp_path, config_dir, world, {CANONICAL_ROOT: 50 * 1024 ** 3})
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 1
    assert "does not exist" in combined
    assert "refusing to fall back" in combined
    assert not world.exists()
    _assert_canonical(canonical_before)


def test_space_cli_missing_local_root_refuses_without_parent_probe(tmp_path):
    base = tmp_path / "run"
    base.mkdir()
    missing_root = base / "missing-worlds"
    config_dir = base / "isolated-config"
    _write_config(config_dir, root=missing_root)
    world = missing_root / "space-world"

    proc = _run_space_cli(
        tmp_path, config_dir, world, {base: 50 * 1024 ** 3})
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 1
    assert "configured worlds root does not exist" in combined
    assert not missing_root.exists()
    assert not world.exists()


def test_space_cli_refuses_disabled_relocated_config_and_guard_bypass(tmp_path):
    base = tmp_path / "run"
    base.mkdir()
    config_dir = base / "isolated-config"
    _write_config(config_dir, root=base / "worlds", enabled=False)
    world = base / "worlds" / "space-world"

    disabled = _run_space_cli(
        tmp_path, config_dir, world, {base: 50 * 1024 ** 3})
    combined = disabled.stdout + disabled.stderr
    assert disabled.returncode == 1
    assert "does not enable the storage guard" in combined
    assert not world.exists()

    driver = _space_driver(tmp_path)
    env = _space_env(tmp_path, config_dir, {base: 50 * 1024 ** 3})
    env["ATOM_WORLD_STORAGE_BYPASS"] = "1"
    bypassed = subprocess.run(
        [sys.executable, str(driver), "space", "--world", str(world),
         "--no-build-cache", "--no-run-data"],
        cwd=BACKEND, env=env, capture_output=True, text=True, timeout=120)
    combined = bypassed.stdout + bypassed.stderr
    assert bypassed.returncode == 1
    assert "ATOM_WORLD_STORAGE_BYPASS" in combined
    assert "refusing to resolve" in combined
    assert not world.exists()


def test_space_cli_dangling_drive_refuses_without_local_fallback(tmp_path):
    base = tmp_path / "run"
    base.mkdir()
    target = base / "unmounted-drive"
    root = base / "dangling-worlds"
    os.symlink(target, root)
    config_dir = base / "isolated-config"
    _write_config(
        config_dir, root=root, top_layout="drive_symlink",
        volume={"mount_point": str(base / "not-mounted"), "name": "Seagate",
                "uuid": "EXPECTED-UUID"})
    world = root / "space-world"

    proc = _run_space_cli(
        tmp_path, config_dir, world, {base: 50 * 1024 ** 3})
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 1
    assert "dangling symlink" in combined
    assert not target.exists()
    assert not world.exists()


def test_space_cli_wrong_uuid_refuses_without_probing_local_parent(tmp_path):
    base = tmp_path / "run"
    base.mkdir()
    mount = base / "mounted"
    mount.mkdir()
    target = base / "drive-target"
    target.mkdir()
    root = base / "drive-worlds"
    os.symlink(target, root)
    config_dir = base / "isolated-config"
    _write_config(
        config_dir, root=root, top_layout="drive_symlink",
        volume={"mount_point": str(mount), "name": "Seagate",
                "uuid": "EXPECTED-UUID"})
    world = root / "space-world"

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    diskutil = fake_bin / "diskutil"
    diskutil.write_text(
        "#!/bin/sh\n"
        "echo \"   Volume Name:   Seagate\"\n"
        "echo \"   Volume UUID:   DIFFERENT-DEVICE\"\n",
        encoding="utf-8",
    )
    diskutil.chmod(0o755)

    driver = _space_driver(tmp_path)
    env = _space_env(tmp_path, config_dir, {base: 50 * 1024 ** 3})
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
    proc = subprocess.run(
        [sys.executable, str(driver), "space", "--world", str(world),
         "--no-build-cache", "--no-run-data"],
        cwd=BACKEND, env=env, capture_output=True, text=True, timeout=120)
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 1
    assert "volume UUID mismatch" in combined
    assert list(target.iterdir()) == []
    assert not world.exists()


def test_estimate_uses_relocated_siblings_and_actual_target_path(
        tmp_path, monkeypatch):
    worlds = tmp_path / "relocated-worlds"
    sibling = worlds / "sibling"
    (sibling / "code").mkdir(parents=True)
    (sibling / "code" / "blob.bin").write_bytes(b"\0" * (7 * SP.MB))
    run_data = sibling / "runs" / "run-aaaaaaaaaaaa" / "data"
    run_data.mkdir(parents=True)
    (run_data / "atom.db").write_bytes(b"\0" * (11 * SP.MB))
    target = worlds / "new-world"

    monkeypatch.setattr(SP, "FRONTEND", tmp_path / "frontend")
    farm = SP.FRONTEND / ".preview-instance" / sibling.name / ".next-preview-x"
    farm.mkdir(parents=True)
    (farm / "chunk.js").write_bytes(b"\0" * (3 * SP.MB))

    est = SP.estimate_world_build(target)
    assert est.target_path == target
    code = next(c for c in est.components if c.name == "code_export")
    run = next(c for c in est.components if c.name == "run_data")
    build = next(c for c in est.components if c.name == "build_cache")
    assert code.measured and code.bytes == 7 * SP.MB and "sibling" in code.source
    assert run.measured and run.bytes == 11 * SP.MB and "sibling" in run.source
    assert build.measured and "sibling" in build.source

    new_run = SP.estimate_new_run(target, with_build_cache=True)
    assert new_run.target_path == target


def test_legacy_world_target_uses_configured_root_not_module_constant(
        tmp_path, monkeypatch):
    base = tmp_path / "run"
    base.mkdir()
    store_root = base / "relocated-worlds"
    store_root.mkdir()
    config_dir = base / "isolated-config"
    _write_config(config_dir, root=store_root)
    monkeypatch.setenv("ATOM_WORLD_STORAGE_PATHS", str(config_dir))
    monkeypatch.setattr(SP, "WORLDS_ROOT", tmp_path / "stale-canonical")

    est = SP.SpaceEstimate(target="world:legacy")
    rep = SP.check_space(est, free_bytes=10 ** 12)
    assert rep.probe_path == store_root.resolve()
    assert rep.probe_source == "configured_worlds_root"


# ---------------------------------------------------------------------------
# negatives: every missing/dangling/wrong root refuses without a fallback
# ---------------------------------------------------------------------------
def test_relocated_missing_root_refused_without_creating_it(tmp_path):
    canonical_before = CANONICAL_ROOT.exists()
    base = tmp_path / "run"
    base.mkdir()
    missing_root = base / "missing-worlds"
    config_dir = base / "isolated-config"
    _write_config(config_dir, root=missing_root)
    world = missing_root / "fresh-world"
    boundary = tmp_path / "server-boundary"

    proc = _run_launcher(
        _base_env(tmp_path, world=world, boundary=boundary,
                  config_dir=config_dir))
    assert proc.returncode != 0
    combined = proc.stdout + proc.stderr
    assert "worlds root does not exist" in combined
    assert not missing_root.exists()
    _assert_no_apps(world, boundary)
    _assert_canonical(canonical_before)


def test_default_missing_canonical_root_refused_not_bootstrapped(tmp_path):
    if CANONICAL_ROOT.exists():
        pytest.skip(
            "the checkout canonical worlds root exists; refusing to probe a "
            "default-layout missing-root case by moving/deleting real data")
    world = CANONICAL_ROOT / "fresh-default-world"
    boundary = tmp_path / "server-boundary"

    proc = _run_launcher(_base_env(tmp_path, world=world, boundary=boundary))
    assert proc.returncode != 0
    combined = proc.stdout + proc.stderr
    assert "worlds root does not exist" in combined
    assert "created configured local worlds root" not in combined
    assert not CANONICAL_ROOT.exists(), (
        "the launcher recreated the canonical worlds root on a default-layout "
        "missing-root run")
    _assert_no_apps(world, boundary)


def test_dangling_relocated_root_refused_without_creating_the_target(tmp_path):
    canonical_before = CANONICAL_ROOT.exists()
    base = tmp_path / "run"
    base.mkdir()
    target = base / "unmounted-volume-worlds"
    root = base / "dangling-worlds"
    os.symlink(target, root)
    config_dir = base / "isolated-config"
    _write_config(config_dir, root=root)
    world = root / "fresh-world"
    boundary = tmp_path / "server-boundary"

    proc = _run_launcher(
        _base_env(tmp_path, world=world, boundary=boundary,
                  config_dir=config_dir))
    assert proc.returncode != 0
    combined = proc.stdout + proc.stderr
    assert "DANGLING" in combined
    assert root.is_symlink()
    assert os.readlink(root) == str(target)
    assert not target.exists()
    _assert_no_apps(world, boundary)
    _assert_canonical(canonical_before)


def test_drive_layout_missing_volume_refused_without_local_fallback(tmp_path):
    canonical_before = CANONICAL_ROOT.exists()
    base = tmp_path / "run"
    base.mkdir()
    root = base / "drive-worlds"
    missing_volume = base / "not-mounted"
    config_dir = base / "isolated-config"
    _write_config(
        config_dir, root=root, top_layout="drive_symlink",
        volume={"mount_point": str(missing_volume), "name": "Seagate",
                "uuid": "EXPECTED-UUID"})
    world = root / "fresh-world"
    boundary = tmp_path / "server-boundary"

    proc = _run_launcher(
        _base_env(tmp_path, world=world, boundary=boundary,
                  config_dir=config_dir))
    assert proc.returncode != 0
    combined = proc.stdout + proc.stderr
    assert "NOT mounted" in combined
    assert not root.exists()
    _assert_no_apps(world, boundary)
    _assert_canonical(canonical_before)


def test_drive_layout_wrong_uuid_refused_without_local_fallback(tmp_path):
    canonical_before = CANONICAL_ROOT.exists()
    base = tmp_path / "run"
    base.mkdir()
    mount = base / "mounted"
    mount.mkdir()
    target = base / "drive-target"
    target.mkdir()
    root = base / "drive-worlds"
    os.symlink(target, root)
    config_dir = base / "isolated-config"
    _write_config(
        config_dir, root=root, top_layout="drive_symlink",
        volume={"mount_point": str(mount), "name": "Seagate",
                "uuid": "EXPECTED-UUID"})
    world = root / "fresh-world"
    boundary = tmp_path / "server-boundary"

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    diskutil = fake_bin / "diskutil"
    diskutil.write_text(
        "#!/bin/sh\n"
        "echo \"   Volume Name:   Seagate\"\n"
        "echo \"   Volume UUID:   DIFFERENT-DEVICE\"\n",
        encoding="utf-8",
    )
    diskutil.chmod(0o755)

    env = _base_env(tmp_path, world=world, boundary=boundary,
                    config_dir=config_dir, extra_path=fake_bin)
    proc = _run_launcher(env)
    assert proc.returncode != 0
    combined = proc.stdout + proc.stderr
    assert "volume UUID mismatch" in combined
    assert root.is_symlink() and root.resolve() == target.resolve()
    assert list(target.iterdir()) == []
    _assert_no_apps(world, boundary)
    _assert_canonical(canonical_before)


def test_top_level_and_worlds_layout_precedence_matches_the_guard(
        tmp_path, monkeypatch):
    validator = _validator_module()
    cases = [
        ("local", "drive_symlink", "drive_symlink"),
        ("drive_symlink", "local", "local"),
        ("local", None, "local"),
    ]
    for top, worlds_layout, expected in cases:
        base = tmp_path / f"case-{top}-{worlds_layout}"
        base.mkdir()
        root = base / "worlds"
        config_dir = base / "isolated-config"
        _write_config(config_dir, root=root, top_layout=top,
                      worlds_layout=worlds_layout)
        monkeypatch.setenv("ATOM_WORLD_STORAGE_PATHS", str(config_dir))
        resolved = validator.resolve_storage_config(REPO)
        assert resolved["layout"] == expected, (
            f"top={top!r} worlds={worlds_layout!r}: validator/guard precedence "
            f"drifted from the guard (got {resolved['layout']!r})")


def test_precedence_launcher_refuses_the_worlds_layout_not_the_top_level(
        tmp_path):
    """The old launcher read the TOP-LEVEL layout first; the guard reads
    ``worlds.layout`` first. A top-level ``local`` must not let the launcher
    create the root when ``worlds.layout`` says drive_symlink."""
    canonical_before = CANONICAL_ROOT.exists()
    base = tmp_path / "run"
    base.mkdir()
    root = base / "mismatched-worlds"
    config_dir = base / "isolated-config"
    _write_config(
        config_dir, root=root, top_layout="local",
        worlds_layout="drive_symlink",
        volume={"mount_point": str(base / "not-mounted"), "name": "Seagate",
                "uuid": "EXPECTED-UUID"})
    world = root / "fresh-world"
    boundary = tmp_path / "server-boundary"

    proc = _run_launcher(
        _base_env(tmp_path, world=world, boundary=boundary,
                  config_dir=config_dir))
    assert proc.returncode != 0
    combined = proc.stdout + proc.stderr
    assert "NOT mounted" in combined
    assert not root.exists(), (
        "the launcher created the root using the top-level layout, while the "
        "guard's worlds.layout precedence refused it")
    _assert_no_apps(world, boundary)
    _assert_canonical(canonical_before)


def test_missing_relocated_config_refuses_instead_of_canonical_fallback(
        tmp_path):
    canonical_before = CANONICAL_ROOT.exists()
    base = tmp_path / "run"
    base.mkdir()
    config_dir = base / "isolated-config"
    config_dir.mkdir()
    world = CANONICAL_ROOT / "would-have-been-canonical"
    boundary = tmp_path / "server-boundary"
    env = _base_env(tmp_path, world=world, boundary=boundary,
                    config_dir=config_dir)

    validator = _run_validator(env, world)
    assert validator.returncode == 2
    combined = validator.stdout + validator.stderr
    assert "does not exist" in combined
    assert "refusing to fall back" in combined

    proc = _run_launcher(env)
    assert proc.returncode != 0
    assert not CANONICAL_ROOT.exists()
    _assert_no_apps(world, boundary)
    _assert_canonical(canonical_before)


def test_root_removed_after_preflight_is_refused_not_recreated(tmp_path):
    """The full guard passed, then the empty root vanished before the mkdir.
    The cheap pre-write assertion must refuse; ``mkdir -p`` must never recreate
    a new empty worlds tree."""
    canonical_before = CANONICAL_ROOT.exists()
    base = tmp_path / "run"
    base.mkdir()
    provision = _run_provisioner(base)
    assert provision.returncode == 0, provision.stderr
    payload = json.loads(provision.stdout)
    store_root = Path(payload["store_root"])
    config_dir = Path(payload["config_path"]).parent
    world = store_root / "fresh-world"
    boundary = tmp_path / "server-boundary"

    env = _base_env(
        tmp_path, world=world, boundary=boundary, config_dir=config_dir,
        remove_root_after_guard=store_root)
    proc = _run_launcher(env)
    assert proc.returncode != 0
    combined = proc.stdout + proc.stderr
    assert "worlds root does not exist" in combined
    assert not store_root.exists(), "the root was recreated after it vanished"
    _assert_no_apps(world, boundary)
    _assert_canonical(canonical_before)
