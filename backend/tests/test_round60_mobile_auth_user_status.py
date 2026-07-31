"""
Round 60 — Mobile auth paths missing user-status check: deactivated users
continue authenticating (Red-Green-Refactor).

R43 added the `user.status != UserStatus.ACTIVE` rejection to
get_current_user / get_current_user_ws / login_for_access_token — but the
three MOBILE authentication paths never got it:

  A. authenticate_mobile_user (core/auth.py) — password login issues fresh
     token pairs for DELETED/SUSPENDED users (the standard login rejects them).
  B. refresh_mobile_token (api/auth_routes.py /mobile/refresh) — renews
     token pairs indefinitely for deactivated users whose device row is
     still active.
  C. authenticate_with_biometric (api/auth_routes.py /mobile/biometric/
     authenticate) — same gap.

A deactivated (departed/removed) employee keeps their password and device —
with these gaps they can keep logging in and minting fresh sessions forever.
Fix mirrors R43: reject non-ACTIVE users at all three entry points.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user as auth_get_current_user
from core.database import get_db
from core.models import UserStatus

SECRET = "secret-mobile-xyz"


def _deactivated_user(status=UserStatus.DELETED):
    user = MagicMock()
    user.id = "u-60"
    user.email = "departed@example.com"
    user.status = status
    return user


class TestMobileLoginStatus:
    def test_mobile_login_rejects_deactivated_user(self):
        import asyncio

        from core.auth import authenticate_mobile_user

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = (
            _deactivated_user()
        )

        result = asyncio.run(
            authenticate_mobile_user(
                email="departed@example.com",
                password="whatever",
                device_token="tok-1",
                platform="ios",
                db=db,
            )
        )

        assert result is None, (
            "authenticate_mobile_user issued tokens to a deactivated user"
        )


class TestMobileRefreshStatus:
    def _client(self, db):
        from api.auth_routes import router

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: db
        return TestClient(app, raise_server_exceptions=False)

    def _refresh_token_for(self, user_id="u-60"):
        import core.auth as auth_mod
        from jose import jwt

        return jwt.encode(
            {
                "sub": user_id,
                "type": "refresh",
                "device_id": "dev-1",
                "exp": datetime.utcnow() + timedelta(days=7),
            },
            auth_mod.SECRET_KEY,
            algorithm="HS256",
        )

    def test_mobile_refresh_rejects_deactivated_user(self):
        db = MagicMock()
        # user query (deactivated) — the endpoint queries User by id
        db.query.return_value.filter.return_value.first.side_effect = [
            _deactivated_user(),
            MagicMock(id="dev-1", status="active"),
        ]
        client = self._client(db)

        resp = client.post(
            "/api/auth/mobile/refresh",
            json={"refresh_token": self._refresh_token_for()},
        )

        assert resp.status_code in (401, 422), (
            f"mobile/refresh issued tokens to a deactivated user "
            f"(got {resp.status_code})"
        )

    def test_biometric_auth_rejects_deactivated_user(self):
        import api.auth_routes as mod

        device = MagicMock()
        device.id = "dev-1"
        device.user_id = "u-60"
        device.status = "active"
        device.device_info = {
            "biometric_public_key": "pubkey",
            "biometric_challenge": "chal",
        }

        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            device,  # device lookup
            _deactivated_user(),  # user lookup
        ]

        app = FastAPI()
        app.include_router(mod.router)
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)

        with patch(
            "api.auth_routes.verify_biometric_signature", return_value=True
        ):
            resp = client.post(
                "/api/auth/mobile/biometric/authenticate",
                json={"device_id": "dev-1", "signature": "sig", "challenge": "chal"},
            )

        assert resp.status_code in (401, 422), (
            f"biometric auth issued tokens to a deactivated user "
            f"(got {resp.status_code})"
        )
