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

import os
import sys
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
WORLD_DB_MARKER = "/whole-app-world/data/atom.db"
#: Same relocation contract as ``core.world_storage_guard``. Recovery must
#: target the root the guard/launcher actually used, never a parallel one.
STORAGE_PATHS_ENV = "ATOM_WORLD_STORAGE_PATHS"


def _load_storage_guard():
    backend = str(BACKEND)
    if backend not in sys.path:
        sys.path.insert(0, backend)
    import core.world_storage_guard as guard
    return guard


def _configured_worlds_root(repo: Path = REPO) -> Path:
    """The canonical worlds root (honours ``ATOM_WORLD_STORAGE_PATHS``)."""
    guard = _load_storage_guard()
    relocated = (os.environ.get(STORAGE_PATHS_ENV) or "").strip()
    config_dir = (Path(relocated).expanduser() if relocated
                  else repo / "backend" / "config")
    try:
        config = guard.load_config(config_dir / "world_storage.json")
    except guard.WorldStorageError:
        # An unreadable config cannot authorize anything; returning the
        # default root makes every path fail the containment check below.
        return (repo / "backend" / "data" / "acceptance_worlds").resolve()
    return Path(config.root).resolve()


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

    worlds_root = _configured_worlds_root(repo)
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
