#!/usr/bin/env python3
"""Set a known password on an ISOLATED scratch world's admin user.

The isolated world may be a copy of a formerly served database (its admin
password is unknown to this worktree) or a freshly bootstrapped acceptance
world (whose password file was lost mid-run). This helper refuses to run
against anything except a scratch-world database, then rotates only that
world's ``admin@example.com`` password using the product's own hasher.

Two layouts are accepted, both proven from the path alone:

  * the historical whole-app world: ``/whole-app-world/data/atom.db``;
  * any world under the configured ``acceptance_worlds`` root, with the
    database at ``<world>/atom.db`` (the layout
    ``scripts/acceptance/launch_integrated_local_candidate.sh`` creates).

The live dev database (``backend/data/atom.db``) is always refused.

Usage:
    DATABASE_URL=sqlite:////private/var/.../whole-app-world/data/atom.db \
        python scripts/acceptance/scratch_admin_password.py

    DATABASE_URL=sqlite:///<repo>/backend/data/acceptance_worlds/<world>/atom.db \
        SCRATCH_ADMIN_PASSWORD=... python scripts/acceptance/scratch_admin_password.py
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any, Optional

REPO = Path(__file__).resolve().parents[2]
VALIDATOR = REPO / "scripts" / "acceptance" / "validate_local_world.py"
WORLD_DB_MARKER = "/whole-app-world/data/atom.db"

_VALIDATOR_MODULE: Optional[Any] = None


def _validator():
    """Load the SAME storage resolver the launcher/guard contract uses."""
    global _VALIDATOR_MODULE
    if _VALIDATOR_MODULE is None:
        spec = importlib.util.spec_from_file_location(
            "validate_local_world", VALIDATOR)
        if spec is None or spec.loader is None:  # pragma: no cover - defensive
            raise RuntimeError(f"cannot load {VALIDATOR}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _VALIDATOR_MODULE = module
    return _VALIDATOR_MODULE


def _configured_worlds_root(repo: Path = REPO) -> Path:
    """The configured worlds root, resolved by the guard's one resolver.

    Honors ``ATOM_WORLD_STORAGE_PATHS`` and its missing-config refusal. The
    recovery helper must never fall back to the canonical root while an
    isolated relocation is declared.
    """
    try:
        return Path(_validator().resolve_storage_config(repo)["root"])
    except Exception as exc:
        raise RuntimeError(
            f"cannot resolve the configured worlds root: {exc}") from exc


def authorized_world_database(
        db_url: str, repo: Path = REPO) -> tuple[bool, str]:
    """Return (allowed, reason). Pure: reads config, opens no database."""
    if not db_url.startswith("sqlite:///"):
        return False, (
            "REFUSED: DATABASE_URL must be an explicit sqlite world database; "
            f"got {db_url.split(':', 1)[0] or 'empty'} scheme")
    raw_path = db_url[len("sqlite:///"):]
    path = Path(raw_path).expanduser()
    try:
        resolved = path.resolve()
    except OSError as exc:
        return False, f"REFUSED: cannot resolve {path}: {exc}"

    live_db = (repo / "backend" / "data" / "atom.db").resolve()
    if resolved == live_db:
        return False, f"REFUSED: {resolved} is the live dev database"

    if WORLD_DB_MARKER in db_url:
        return True, "historical isolated whole-app world"

    worlds_root = None
    try:
        worlds_root = _configured_worlds_root(repo)
    except RuntimeError as exc:
        return False, f"REFUSED: {exc}"
    if worlds_root not in resolved.parents:
        return False, (
            f"REFUSED: {resolved} is not under the configured worlds root "
            f"{worlds_root}")
    if resolved.parent == worlds_root or resolved.name != "atom.db":
        return False, (
            "REFUSED: a world database must be <world>/atom.db under the "
            f"configured worlds root, got {resolved}")
    # The configured local worlds root itself lives under backend/data; that
    # layout is the documented one, so being under backend/data is only a
    # refusal when the path is not also a world under that root (already
    # checked above). The live database file was refused explicitly.
    return True, "scratch world under the configured worlds root"


def _refusal_reason(db_url: str) -> Optional[str]:
    allowed, reason = authorized_world_database(db_url)
    return None if allowed else reason


def main() -> int:
    db_url = os.getenv("DATABASE_URL", "")
    refusal = _refusal_reason(db_url)
    if refusal:
        print(refusal, file=sys.stderr)
        return 2

    # Import after the guard: importing core.database binds the engine.
    from core.auth import get_password_hash
    from core.database import get_db_session
    from core.models import User

    password = os.getenv("SCRATCH_ADMIN_PASSWORD")
    if not password:
        print("REFUSED: set SCRATCH_ADMIN_PASSWORD in the environment", file=sys.stderr)
        return 4
    email = os.getenv("SCRATCH_USER_EMAIL", "admin@example.com")
    with get_db_session() as db:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            print(f"REFUSED: {email} is not present in this world", file=sys.stderr)
            return 3
        user.hashed_password = get_password_hash(password)
        user.status = "active"
        db.commit()
        role = getattr(user.role, "value", user.role)
        print(f"rotated scratch password for {user.email} role={role}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
