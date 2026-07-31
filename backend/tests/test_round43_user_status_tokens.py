"""
Round 43 — Deleted/suspended-user token continuation (Red-Green-Refactor).

`login_for_access_token` rejects non-ACTIVE users, but `get_current_user` and
`get_current_user_ws` never check `user.status` — so an already-issued JWT
(valid for 24h) keeps authenticating a user after an admin soft-deletes the
account (`enterprise_user_management.deactivate_user` sets status=DELETED) or
suspends it. Every endpoint protected by `get_current_user` (which includes
`get_current_session_token` and `require_permission` chains) is affected.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import jwt as pyjwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import ALGORITHM, get_current_user_ws
from core.database import get_db


def make_token(user_id: str, jti: str = "jti-1") -> str:
    # Read SECRET_KEY at call time — test_auth_fixes reloads core.auth mid-
    # session, so a module-level constant can go stale (decode failures).
    import core.auth as auth_mod

    return pyjwt.encode(
        {
            "sub": user_id,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "jti": jti,
        },
        auth_mod.SECRET_KEY,
        algorithm=ALGORITHM,
    )


class FakeUser:
    def __init__(self, user_id: str, status: str):
        self.id = user_id
        self.status = status
        self.email = "u@example.com"
        self.first_name = "Test"
        self.last_name = "User"
        self.role = "member"
        self.email_verified = True
        self.tenant_id = None
        self.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.last_login = None


def make_client(user_status: str):
    """App with real get_current_user; db returns a user with given status."""
    from api.user_management_routes import router

    app = FastAPI()
    app.include_router(router)
    user = FakeUser("u-1", user_status)

    def _override_db():
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = user
        return db

    app.dependency_overrides[get_db] = _override_db
    return TestClient(app, raise_server_exceptions=False)


class TestUserStatusTokenEnforcement:
    def test_active_user_token_accepted(self):
        resp = make_client("active").get(
            "/api/users/me", headers={"Authorization": f"Bearer {make_token('u-1')}"}
        )
        assert resp.status_code == 200

    def test_suspended_user_token_rejected(self):
        resp = make_client("suspended").get(
            "/api/users/me", headers={"Authorization": f"Bearer {make_token('u-1')}"}
        )
        assert resp.status_code == 401

    def test_deleted_user_token_rejected(self):
        resp = make_client("deleted").get(
            "/api/users/me", headers={"Authorization": f"Bearer {make_token('u-1')}"}
        )
        assert resp.status_code == 401

    def test_pending_user_token_rejected(self):
        resp = make_client("pending").get(
            "/api/users/me", headers={"Authorization": f"Bearer {make_token('u-1')}"}
        )
        assert resp.status_code == 401

    def test_websocket_rejects_suspended(self):
        import asyncio

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = FakeUser(
            "u-1", "suspended"
        )
        result = asyncio.run(get_current_user_ws(make_token("u-1"), db))
        assert result is None

    def test_websocket_accepts_active(self):
        import asyncio

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = FakeUser(
            "u-1", "active"
        )
        result = asyncio.run(get_current_user_ws(make_token("u-1"), db))
        assert result is not None
