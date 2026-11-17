#!/usr/bin/env python3
"""Provision one explicit, isolated acceptance-worlds store.

Why this command exists
-----------------------
The integrated launcher and the canvas acceptance harness no longer create a
missing worlds root. That convenience bootstrap was the silent-empty-store
hazard: it read ``backend/config/world_storage.json`` directly (ignoring
``ATOM_WORLD_STORAGE_PATHS`` and using a different ``layout`` precedence),
then ``mkdir -p``'d the checkout's canonical
``backend/data/acceptance_worlds`` before the real
``core.world_storage_guard`` preflight could refuse. A run could then "pass"
against a brand-new empty tree.

A fresh isolated journey is still fully supported — it just has to be
provisioned explicitly, in an already-owned temporary directory, with the
config OUTSIDE the store root:

    RUN_DIR=/absolute/existing/owned/temp/run
    python scripts/acceptance/provision_isolated_world_store.py \
        --base "$RUN_DIR" --name isolated-worlds \
        --config-dir "$RUN_DIR/isolated-config"
    export ATOM_WORLD_STORAGE_PATHS="$RUN_DIR/isolated-config"
    export WORLD="$RUN_DIR/isolated-worlds/<new-world>"

This command creates only:

* ``<base>/<name>`` — the empty store root (intentional fixture
  initialization, never the canonical repo root);
* ``<config-dir>/world_storage.json`` — the guard config, outside the store
  root.

It never creates a world child, never adopts an existing non-empty tree,
never overwrites a differing config, and never runs with the guard bypass.
After writing, it runs the real ``core.world_storage_guard`` preflight against
the generated config and exits non-zero if the guard refuses.

Refusals (exit 2) are expected and actionable. Nothing is written before the
path and ownership checks pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
CANONICAL_ROOT = BACKEND / "data" / "acceptance_worlds"
STORAGE_PATHS_ENV = "ATOM_WORLD_STORAGE_PATHS"
BYPASS_ENV = "ATOM_WORLD_STORAGE_BYPASS"
SCHEMA = "atom-isolated-world-store-1"


class ProvisionError(RuntimeError):
    """A refusal that must stop provisioning before/without an unsafe write."""


def _resolved(path: Path) -> Path:
    try:
        return path.expanduser().resolve(strict=False)
    except OSError as exc:
        raise ProvisionError(f"cannot resolve {path}: {exc}") from exc


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _load_guard(config_dir: Path):
    """Import the real guard with its config/lock paths relocated.

    The relocation env is set BEFORE the import because the guard binds all
    four paths at import time. This process only; the operator exports the
    same value for the launcher (the success output prints the exact line).
    """
    current = (os.environ.get(STORAGE_PATHS_ENV) or "").strip()
    if current and _resolved(Path(current)) != config_dir:
        raise ProvisionError(
            f"{STORAGE_PATHS_ENV} is already set to {current}; refusing to "
            f"provision {config_dir} under a different relocation. Unset it "
            f"or pass the matching --config-dir.")
    if os.environ.get(BYPASS_ENV):
        raise ProvisionError(
            f"{BYPASS_ENV} is set; refusing to provision a store while the "
            f"storage guard is bypassed.")

    os.environ[STORAGE_PATHS_ENV] = str(config_dir)
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    import core.world_storage_guard as guard

    expected = config_dir / "world_storage.json"
    if _resolved(Path(guard.CONFIG_PATH)) != expected:
        raise ProvisionError(
            f"guard config path is {guard.CONFIG_PATH}, expected {expected}; "
            f"refusing to provision against a different guard contract")
    return guard


def _protected_roots(guard) -> List[Path]:
    """The canonical root plus the checkout's configured root, resolved."""
    roots = {_resolved(CANONICAL_ROOT)}
    checkout = BACKEND / "config" / "world_storage.json"
    try:
        configured = guard.load_config(checkout)
    except guard.WorldStorageError:
        # A corrupt checkout config is not authority to relax protection; the
        # canonical default above still applies.
        configured = None
    if configured is not None:
        roots.add(_resolved(Path(configured.root)))
    return sorted(roots)


def _config_text(store_root: Path) -> str:
    payload = {
        "_comment": [
            "Explicit isolated acceptance-worlds store.",
            "Provisioned with scripts/acceptance/provision_isolated_world_store.py.",
            "This config is OUTSIDE the worlds root on purpose; backend/data is",
            "gitignored and is the tree that moves. The integrated launcher runs",
            "this guard before it creates anything, and a missing root is a",
            "refusal - never a convenience bootstrap.",
        ],
        "enabled": True,
        "layout": "local",
        "worlds": {"root": str(store_root)},
        "symlink_sample": 25,
        "fail_on_broken_symlinks": False,
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def provision(base: Path, name: str, config_dir: Path) -> Dict[str, Any]:
    """Create an empty isolated store + config, then verify with the guard."""
    raw_base = Path(base).expanduser()
    raw_config_dir = Path(config_dir).expanduser()
    if not raw_base.is_absolute():
        raise ProvisionError(f"--base must be an absolute path: {raw_base}")
    if not raw_config_dir.is_absolute():
        raise ProvisionError(
            f"--config-dir must be an absolute path: {raw_config_dir}")
    base = _resolved(raw_base)
    config_dir = _resolved(raw_config_dir)
    if not base.is_dir():
        raise ProvisionError(
            f"--base must be an existing owned directory (not created here): "
            f"{base}")
    if not name or name in (".", "..") or Path(name).name != name:
        raise ProvisionError(f"--name must be one directory name, got {name!r}")

    repo = _resolved(REPO)
    if base == repo or _is_within(base, repo):
        raise ProvisionError(
            f"--base {base} is inside the checkout {repo}; provision an "
            f"isolated store only under an existing owned TEMPORARY directory "
            f"outside the repo")
    if config_dir == repo or _is_within(config_dir, repo):
        raise ProvisionError(
            f"--config-dir {config_dir} is inside the checkout {repo}; the "
            f"config must live outside both the repo tree and the worlds root")

    store_root = base / name
    if store_root.exists():
        if not store_root.is_dir() or store_root.is_symlink():
            raise ProvisionError(
                f"store root exists and is not a real directory: {store_root}")
        entries = list(store_root.iterdir())
        if entries:
            raise ProvisionError(
                f"store root is not empty ({len(entries)} entr(y/ies)): "
                f"{store_root}. Refusing to adopt an existing tree as a fresh "
                f"isolated store.")
    if config_dir == store_root or _is_within(config_dir, store_root):
        raise ProvisionError(
            f"--config-dir {config_dir} is inside the store root {store_root}; "
            f"the config must live OUTSIDE the movable worlds tree")

    config_file = config_dir / "world_storage.json"
    if config_dir.exists():
        if not config_dir.is_dir() or config_dir.is_symlink():
            raise ProvisionError(
                f"config dir exists and is not a real directory: {config_dir}")
    elif not config_dir.parent.is_dir():
        raise ProvisionError(
            f"config dir parent does not exist: {config_dir.parent}. Create "
            f"only the final config directory under an existing owned temp dir.")

    # Import AFTER the env is set, then re-check protection with the guard's
    # own canonical/config-derived roots before the first write.
    guard = _load_guard(config_dir)
    protected = _protected_roots(guard)
    for protected_root in protected:
        if store_root == protected_root or _is_within(store_root, protected_root):
            raise ProvisionError(
                f"store root {store_root} is the canonical/configured worlds "
                f"root ({protected_root}) or inside it. This command never "
                f"creates the canonical acceptance_worlds tree; declare an "
                f"explicit isolated root instead.")
        if base == protected_root or _is_within(base, protected_root):
            raise ProvisionError(
                f"--base {base} is inside the canonical/configured worlds root "
                f"{protected_root}; use an owned temporary directory outside it")

    desired = _config_text(store_root)
    if config_file.exists():
        try:
            existing = config_file.read_text()
        except OSError as exc:
            raise ProvisionError(f"cannot read {config_file}: {exc}") from exc
        if existing != desired:
            raise ProvisionError(
                f"{config_file} already exists with different content; "
                f"refusing to overwrite a declared store config")
        created_config = False
    else:
        created_config = True

    created_root = False
    created_config_dir = False
    try:
        if not store_root.exists():
            store_root.mkdir()
            created_root = True
        if not config_dir.exists():
            config_dir.mkdir()
            created_config_dir = True
        if created_config:
            tmp = config_file.with_name(config_file.name + ".tmp")
            tmp.write_text(desired)
            os.replace(tmp, config_file)

        # The REAL guard preflight, against the generated config. This also
        # catches the interlock/volume/layout contract.
        report = guard.preflight()
    except Exception as exc:
        # Do not leave a half-provisioned store behind. Only artifacts this
        # invocation created are removed, and only when they are still empty.
        if created_config:
            config_file.unlink(missing_ok=True)
        if created_root and store_root.is_dir() and not any(store_root.iterdir()):
            store_root.rmdir()
        if created_config_dir and config_dir.is_dir() and not any(config_dir.iterdir()):
            config_dir.rmdir()
        if isinstance(exc, ProvisionError):
            raise
        raise ProvisionError(str(exc)) from exc

    return {
        "schema": SCHEMA,
        "base": str(base),
        "store_root": str(store_root),
        "config_dir": str(config_dir),
        "config_path": str(config_file),
        "config_sha256": hashlib.sha256(config_file.read_bytes()).hexdigest(),
        "layout": "local",
        "guard": report.summary().splitlines()[0] if report.summary() else "ok",
        "guard_summary": report.summary(),
        "canonical_root": str(_resolved(CANONICAL_ROOT)),
        "canonical_root_created": False,
        "created": {
            "store_root": created_root,
            "config_dir": created_config_dir,
            "config": created_config,
        },
        "export": f'export {STORAGE_PATHS_ENV}="{config_dir}"',
        "next": (
            f'export WORLD="{store_root}/<new-world>"  '
            f"# the launcher creates this world CHILD after the guard passes"
        ),
    }


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Provision an explicit isolated acceptance-worlds store.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--base", required=True,
        help="existing owned temporary directory (never created here)")
    ap.add_argument(
        "--name", default="isolated-worlds",
        help="one directory name for the empty store root under --base")
    ap.add_argument(
        "--config-dir", default=None,
        help="existing temp base for the config (default: <base>/isolated-config); "
             "must be OUTSIDE the store root")
    args = ap.parse_args(argv)

    base = Path(args.base)
    config_dir = Path(args.config_dir) if args.config_dir else base / "isolated-config"
    try:
        payload = provision(base, args.name, config_dir)
    except ProvisionError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
