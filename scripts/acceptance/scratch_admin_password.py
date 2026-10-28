#!/usr/bin/env python3
"""Set a known password on the ISOLATED whole-app world's admin user.

The isolated world is a copy of a formerly served database, so its admin
password is not known to this worktree (and must not be copied from any live
credential). This helper refuses to run against anything except the declared
scratch world path, then rotates only that world's ``admin@example.com``
password using the product's own hasher.

Usage:
    DATABASE_URL=sqlite:////private/var/.../whole-app-world/data/atom.db \
        python scripts/acceptance/scratch_admin_password.py
"""
from __future__ import annotations

import os
import sys

WORLD_DB_MARKER = "/whole-app-world/data/atom.db"


def main() -> int:
    db_url = os.getenv("DATABASE_URL", "")
    if WORLD_DB_MARKER not in db_url:
        print(
            f"REFUSED: DATABASE_URL does not point at the isolated world "
            f"({WORLD_DB_MARKER}). Got: {db_url!r}",
            file=sys.stderr,
        )
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
