#!/usr/bin/env python3
"""Preflight for the integrated-local launcher.

Refuses protected/ambiguous paths, unsafe reuse, occupied ports and low disk
space BEFORE the shell launcher writes anything. Emits one JSON object on
success so the launcher can persist the exact identity it validated.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

MARKER = ".atom-integrated-world.json"
SECRET_FILE = ".atom-secret"
#: Same relocation contract as ``core.world_storage_guard``.
STORAGE_PATHS_ENV = "ATOM_WORLD_STORAGE_PATHS"


def fail(message: str) -> "None":
    print(f"REFUSED: {message}", file=sys.stderr)
    raise SystemExit(2)


def real(path: Path) -> Path:
    try:
        return path.expanduser().resolve(strict=False)
    except OSError as exc:
        fail(f"cannot resolve {path}: {exc}")


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _storage_config(repo: Path) -> dict:
    """Read the config the storage guard will read (env relocation included)."""
    import core.world_storage_guard as guard  # sys.path inserted below

    relocated = (os.environ.get(STORAGE_PATHS_ENV) or "").strip()
    config_dir = (Path(relocated).expanduser() if relocated
                  else repo / "backend" / "config")
    try:
        config = guard.load_config(config_dir / "world_storage.json")
    except guard.WorldStorageError as exc:
        fail(str(exc))
    return {
        "config_path": str(config_dir / "world_storage.json"),
        "relocated_by_env": bool(relocated),
        "layout": config.layout,
        "root": str(real(Path(config.root))),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--backend-port", type=int, required=True)
    ap.add_argument("--frontend-port", type=int, required=True)
    ap.add_argument("--min-free-mb", type=int, default=1024)
    args = ap.parse_args()

    repo = real(Path(args.repo))
    world = real(Path(args.world))
    home = real(Path.home())

    # The world must live under the SAME configured worlds root the storage
    # guard protects, resolved through the SAME relocation contract. Reading
    # only the checkout config here would let the guard validate a relocated
    # root while the launcher validated (and refused) another.
    backend_dir = repo / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    storage = _storage_config(repo)
    configured_root = Path(storage["root"])

    protected = {
        Path("/"),
        home,
        repo,
        repo / "backend",
        repo / "backend" / "data",
        configured_root,
        repo / "frontend-nextjs",
        repo / "docs",
        repo / "scripts",
    }
    if world in protected:
        fail(f"{world} is a protected repository/home/worlds-root path")
    for base in (repo / "backend" / "data", repo / "frontend-nextjs"):
        try:
            world.relative_to(base)
        except ValueError:
            pass
        else:
            if base == repo / "backend" / "data":
                try:
                    world.relative_to(configured_root)
                except ValueError:
                    fail(f"{world} is inside protected tree {base} but not "
                         f"under the configured worlds root {configured_root}")
            else:
                fail(f"{world} is inside protected tree {base}")
    try:
        world.relative_to(configured_root)
    except ValueError:
        fail(f"{world} must be under the configured worlds root "
             f"{configured_root}")
    if world.name in {".", ".."} or world.name.endswith(".db"):
        fail(f"{world} is not a world directory")
    if world.exists() and not world.is_dir():
        fail(f"{world} exists and is not a directory")
    if world.is_symlink():
        # A symlink is allowed only when it resolves to a non-protected,
        # non-repository path; `world` is already resolved above.
        pass

    fresh = not world.exists() or not any(world.iterdir())
    marker_path = world / MARKER
    marker = None
    if not fresh:
        if not marker_path.is_file():
            fail(
                f"{world} is non-empty and has no {MARKER}; refusing to reuse "
                "an unknown database/world")
        try:
            marker = json.loads(marker_path.read_text())
        except (OSError, ValueError) as exc:
            fail(f"cannot read {marker_path}: {exc}")
        expected = {
            "world": str(world),
            "repo": str(repo),
            "database": str(world / "atom.db"),
        }
        for key, value in expected.items():
            if str(marker.get(key) or "") != value:
                fail(
                    f"{marker_path} {key}={marker.get(key)!r} does not match "
                    f"{value!r}")
        for pid_name, label in (("backend.pid", "backend"),
                                ("frontend.pid", "frontend")):
            pid_file = world / pid_name
            if not pid_file.is_file():
                continue
            try:
                pid = int(pid_file.read_text().strip())
            except (OSError, ValueError):
                continue
            if pid > 1 and Path(f"/proc/{pid}").exists():
                fail(f"{label} pid {pid} from {pid_file} is still alive")
            # macOS has no /proc; use a kill(0) probe as a portable fallback.
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                pass
            except PermissionError:
                fail(f"{label} pid {pid} is alive but not owned by this user")
            else:
                fail(f"{label} pid {pid} from {pid_file} is still alive")

    if port_open(args.backend_port):
        fail(f"backend port {args.backend_port} is already in use")
    if port_open(args.frontend_port):
        fail(f"frontend port {args.frontend_port} is already in use")

    probe = world
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    free_bytes = shutil.disk_usage(str(probe)).free
    minimum = args.min_free_mb * 1024 * 1024
    if free_bytes < minimum:
        fail(
            f"only {free_bytes // (1024 * 1024)} MiB free at {world}; "
            f"need at least {args.min_free_mb} MiB")

    payload = {
        "schema": "atom-integrated-local-world-1",
        "world": str(world),
        "repo": str(repo),
        "database": str(world / "atom.db"),
        "configured_worlds_root": str(configured_root),
        "storage_config": storage,
        "fresh": fresh,
        "marker": str(marker_path),
        "secret_file": str(world / SECRET_FILE),
        "backend_port": args.backend_port,
        "frontend_port": args.frontend_port,
        "free_bytes": free_bytes,
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "prior": marker or {},
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
