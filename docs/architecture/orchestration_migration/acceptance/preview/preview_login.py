#!/usr/bin/env python3
"""Make the preview world loggable, then log in through the REAL endpoint.

Two things this does, both scoped to the disposable preview world only:

1. Sets a KNOWN password for the preview's admin user. The world is a copy of
   the developer's database, so the admin password is the developer's and is
   not knowable here. The alternative — minting a JWT out-of-process — failed
   for a real reason: the server derives its signing key at startup, and a
   client process cannot be guaranteed to hold the same one. Setting a password
   and calling the app's own `/api/auth/login` exercises the genuine auth path
   and removes an entire class of confusing failure.
   The user's real database is never opened; only the preview world's own run
   directory is written.

2. Logs in and prints nothing but a success flag and the token LENGTH, so no
   credential material is ever echoed into a log or a report.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

PREVIEW_USER = "admin@example.com"
PREVIEW_PASSWORD = "preview-only-local-2026"


def main() -> int:
    import httpx

    state = json.loads((HERE / "preview_state.json").read_text())
    db_path = state["isolation"]["db_path"]
    if "acceptance_worlds" not in db_path:
        raise SystemExit(f"refusing to write outside a preview world: {db_path}")

    # TESTING must NOT be set: core/database.py treats TESTING=1 as "force the
    # scratch test DB" and OVERRIDES DATABASE_URL, so a write lands in
    # backend/test_integration.db instead of the preview world. The isolation
    # here comes from an explicit DATABASE_URL, which is what the server itself
    # uses.
    os.environ.pop("TESTING", None)
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["SECRET_KEY"] = state.get("preview_secret_key", "")
    os.environ["ENVIRONMENT"] = "development"

    from core.auth import get_password_hash
    from core.database import get_db_session
    from core.models import User

    with get_db_session() as db:
        user = db.query(User).filter(User.email == PREVIEW_USER).first()
        if user is None:
            raise SystemExit(f"{PREVIEW_USER} not in the preview world")
        user.hashed_password = get_password_hash(PREVIEW_PASSWORD)
        db.commit()
        print(f"[world] password set for {PREVIEW_USER} in the preview world only")

    base = f"http://127.0.0.1:{state['backend_port']}"
    # JSON, and the field is `username` (OAuth2PasswordRequestForm shape but
    # parsed from a JSON body here — a form-encoded POST is rejected 422).
    r = httpx.post(f"{base}/api/auth/login",
                   json={"username": PREVIEW_USER, "password": PREVIEW_PASSWORD},
                   headers={"Origin": f"http://localhost:{state['frontend_port']}",
                            "Content-Type": "application/json"},
                   timeout=60, trust_env=False)
    if r.status_code != 200:
        print(f"[login] FAILED HTTP {r.status_code}: {r.text[:300]}")
        return 1
    body = r.json()
    token = body.get("access_token") or body.get("token") or ""
    print(f"[login] OK — access_token received ({len(token)} chars), "
          f"token_type={body.get('token_type')}")
    if not token:
        print("[login] response carried no access token:", json.dumps(body)[:300])
        return 1
    me = httpx.get(f"{base}/api/auth/me",
                   headers={"Authorization": f"Bearer {token}",
                            "Origin": f"http://localhost:{state['frontend_port']}"},
                   timeout=30, trust_env=False)
    print(f"[login] /api/auth/me -> HTTP {me.status_code} "
          f"{me.text[:160] if me.status_code != 200 else ''}")
    return 0 if me.status_code == 200 else 2


if __name__ == "__main__":
    raise SystemExit(main())
