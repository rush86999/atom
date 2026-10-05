"""Round 18 (2026-10-02): the integrations UI said "Connected" while the
provider refused the token refresh, and TokenRefreshWorker logged "grant
may need a manual reconnect" every cycle for a healthy grant.

Three defects, pinned here:
1. ZohoAdapter.refresh_token() never loaded its token row — a cold
   adapter (exactly what the worker builds) returned False instantly,
   without any network call, so the suite rows sat expired forever.
2. /api/v1/auth/oauth/tokens reported the legacy is_active flag, which
   only flips on explicit disconnect — the badge stayed green for weeks
   after the grant actually died (access_token_expires_at read
   2026-09-05 on a live box). _zoho_grant_health() overrides it with
   live integration_tokens state.
3. get_team_folders' /users/me fallback synthesized a team dict with no
   attributes, so every folder showed the raw 34-char team id where the
   team name belongs.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _row(provider, *, refresh="rt-plain", expires_in_s, db_session_extra=None):
    from core.models import IntegrationToken

    return IntegrationToken(
        tenant_id="t1",
        workspace_id="default",
        provider=provider,
        access_token="at-old",
        refresh_token=refresh,
        token_type="Bearer",
        status="active",
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in_s),
    )


def _ok_token_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json = lambda: {"access_token": "fresh-at", "expires_in": 3600}
    return resp


class TestColdAdapterRefresh:
    """The worker builds ZohoAdapter(db=..., workspace_id=...) and calls
    refresh_token() directly — no data fetch, no ensure_token()."""

    async def test_cold_adapter_loads_row_and_refreshes(self, db_session):
        from core.integrations.adapters.zoho import ZohoAdapter
        from core.models import IntegrationToken

        db_session.add(_row("zoho", expires_in_s=120))
        db_session.add(_row("zoho_crm", expires_in_s=120))
        db_session.commit()

        adapter = ZohoAdapter(db=db_session, workspace_id="default")
        posted = {}

        async def fake_post(self_client, url, data=None, **kw):
            posted["url"] = url
            posted["data"] = data
            return _ok_token_response()

        with patch(
            "core.integrations.adapters.zoho.httpx.AsyncClient.post",
            new=fake_post,
        ):
            assert await adapter.refresh_token() is True

        assert posted["data"]["grant_type"] == "refresh_token"
        assert posted["data"]["refresh_token"] == "rt-plain"
        # Canonical row persisted the fresh token; family row fanned out.
        rows = {
            r.provider: r
            for r in db_session.query(IntegrationToken).filter(
                IntegrationToken.provider.like("zoho%")).all()
        }
        from core.privsec.token_encryption import decrypt_token

        assert decrypt_token(rows["zoho"].access_token, allow_plaintext=True) == "fresh-at"
        assert decrypt_token(rows["zoho_crm"].access_token, allow_plaintext=True) == "fresh-at"
        exp = rows["zoho"].expires_at
        if exp and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        assert exp > datetime.now(timezone.utc) + timedelta(minutes=30)

    async def test_cold_adapter_without_row_returns_false_no_network(self, db_session):
        from core.integrations.adapters.zoho import ZohoAdapter

        adapter = ZohoAdapter(db=db_session, workspace_id="default")

        async def explode(*a, **kw):
            raise AssertionError("refresh must not hit the network without a grant")

        with patch(
            "core.integrations.adapters.zoho.httpx.AsyncClient.post", new=explode
        ):
            assert await adapter.refresh_token() is False


class TestWorkerCycle:
    """refresh_expiring_tokens must actually refresh (it returned False
    every cycle before the cold-load fix) and log success."""

    async def test_worker_refreshes_expiring_rows(self, db_session):
        from core.integrations.adapters.zoho import ZohoAdapter
        from core.models import IntegrationToken
        from workers.token_refresh_worker import TokenRefreshWorker

        db_session.add(_row("zoho", expires_in_s=120))
        db_session.commit()

        real_adapter = ZohoAdapter(db=db_session, workspace_id="default")

        class Factory:
            def __call__(self, db=None, workspace_id=None, **kw):
                return real_adapter

        class DelegateSession:
            """Worker-owned view of the test session: queries hit the real
            rows; close() is a no-op so the fixture still owns teardown."""

            def __init__(self, real):
                self._real = real

            def __getattr__(self, name):
                if name == "close":
                    return lambda: None
                return getattr(self._real, name)

        with patch(
            "core.database.SessionLocal", lambda: DelegateSession(db_session)
        ), patch(
            "core.integrations.adapters.zoho.ZohoAdapter", Factory()
        ), patch(
            "core.integrations.adapters.zoho.httpx.AsyncClient.post",
            new=AsyncMock(return_value=_ok_token_response()),
        ):
            await TokenRefreshWorker().refresh_expiring_tokens()

        # Success is the persisted refresh (before the cold-load fix the
        # worker's adapter had no token and returned False every cycle).
        row = db_session.query(IntegrationToken).filter_by(provider="zoho").one()
        from core.privsec.token_encryption import decrypt_token

        assert decrypt_token(row.access_token, allow_plaintext=True) == "fresh-at"


class TestZohoGrantHealth:
    async def test_fresh_row_is_active(self, db_session):
        from api.oauth_routes import _zoho_grant_health

        db_session.add(_row("zoho", expires_in_s=1800))
        db_session.commit()
        assert _zoho_grant_health(db_session)["status"] == "active"

    async def test_one_fresh_family_row_keeps_grant_active(self, db_session):
        from api.oauth_routes import _zoho_grant_health

        # Suite rows long dead, WorkDrive row refreshed on demand and alive.
        db_session.add(_row("zoho", expires_in_s=-3600))
        db_session.add(_row("zoho_workdrive", expires_in_s=1800))
        db_session.commit()
        assert _zoho_grant_health(db_session)["status"] == "active"

    async def test_all_rows_expired_past_grace_is_expired(self, db_session):
        from api.oauth_routes import _zoho_grant_health

        db_session.add(_row("zoho", expires_in_s=-3600))
        db_session.add(_row("zoho_workdrive", expires_in_s=-1800))
        db_session.commit()
        assert _zoho_grant_health(db_session)["status"] == "expired"

    async def test_recently_expired_within_grace_still_active(self, db_session):
        from api.oauth_routes import _zoho_grant_health

        db_session.add(_row("zoho", expires_in_s=-120))
        db_session.commit()
        assert _zoho_grant_health(db_session)["status"] == "active"

    async def test_no_rows_falls_back_to_none(self, db_session):
        from api.oauth_routes import _zoho_grant_health

        assert _zoho_grant_health(db_session) is None


class TestTeamFolderFallbackName:
    async def test_users_me_fallback_uses_org_name(self):
        from integrations.zoho_workdrive_service import ZohoWorkDriveService

        svc = ZohoWorkDriveService()
        org_id = "5fx4k0dfb2ab8e65446678aa72369b929a341"

        def fake_get(url, **kw):
            resp = MagicMock()
            resp.status_code = 200
            if url.endswith("/teams"):
                resp.json = lambda: {"data": []}
            elif url.endswith("/users/me"):
                resp.json = lambda: {"data": {"attributes": {
                    "preferred_team_id": org_id,
                    "last_viewed_org_info": {
                        "org_id": org_id,
                        "org_name": "Brennan Machinery Inc.",
                    },
                }}}
            else:
                resp.json = lambda: {"data": [{
                    "id": "folder-own-id-1",
                    "type": "teamfolders",
                    "attributes": {"name": "Accounting"},
                }]}
            return resp

        with patch.object(
            svc, "get_access_token", new=AsyncMock(return_value="tok")
        ), patch.object(svc.client, "get", side_effect=fake_get):
            folders = await svc.get_team_folders("u1")

        assert len(folders) == 1
        assert folders[0]["id"] == "folder-own-id-1"
        assert folders[0]["team_name"] == "Brennan Machinery Inc."
        assert folders[0]["team_id"] == org_id

    async def test_missing_org_name_falls_back_to_team_id(self):
        from integrations.zoho_workdrive_service import ZohoWorkDriveService

        svc = ZohoWorkDriveService()
        org_id = "5fx4k0dfb2ab8e65446678aa72369b929a341"

        def fake_get(url, **kw):
            resp = MagicMock()
            resp.status_code = 200
            if url.endswith("/teams"):
                resp.json = lambda: {"data": []}
            elif url.endswith("/users/me"):
                resp.json = lambda: {"data": {"attributes": {
                    "preferred_team_id": org_id,
                }}}
            else:
                resp.json = lambda: {"data": [{
                    "id": "f1", "type": "teamfolders",
                    "attributes": {"name": "General"},
                }]}
            return resp

        with patch.object(
            svc, "get_access_token", new=AsyncMock(return_value="tok")
        ), patch.object(svc.client, "get", side_effect=fake_get):
            folders = await svc.get_team_folders("u1")

        # Same failure mode as before ONLY when Zoho truly sends no name —
        # but the folder's own id stays its own.
        assert folders[0]["team_name"] == org_id
        assert folders[0]["id"] == "f1"
