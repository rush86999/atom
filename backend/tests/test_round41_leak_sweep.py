"""
Round 41 — str(e) leak sweep: exception text reaching clients via response
messages/details (Red-Green-Refactor).

Round 18 fixed 992 str(e) leaks, but code added since (Rounds 19-40)
re-introduced client-visible leaks in mounted routers:

  A. api/canvas_recording_routes.py — start/event/stop/get/list all return
     `message=f"Failed to ...: {str(e)}"` (R38's sweep missed these 5).
  B. api/social_media_routes.py — per-platform poster exceptions surface
     `{"error": str(e)}` in platform_results, and the outer 500 handler
     leaks via `details={"error": str(e)}`.
  C. api/admin_routes.py — bulk_resolve_conflicts appends
     `f"Conflict {id}: {str(e)}"` to the client-visible errors list.

Excluded as NOT leaks (reviewed): social_media validate_content echoes the
client's own platform name; recording_review_routes echoes the client's own
recording_id; device_capabilities uses str(e) for flow control only.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user as auth_get_current_user
from core.database import get_db

SENTINEL = "SENTINEL_LEAK_round41"


def make_client(router, current_user=None, db=None):
    """TestClient with auth + db dependency overrides (authenticated)."""
    app = FastAPI()
    app.include_router(router)

    def _override_user():
        if current_user is not None:
            return current_user
        user = MagicMock(id="r41-user")
        user.role = "super_admin"
        return user

    def _override_db():
        return db if db is not None else MagicMock()

    app.dependency_overrides[auth_get_current_user] = _override_user
    app.dependency_overrides[get_db] = _override_db
    return TestClient(app, raise_server_exceptions=False)


# ============================================================================
# A. Canvas recording — 5 client-visible str(e) messages
# ============================================================================

class TestCanvasRecordingLeaks:
    def _client_with_raising_service(self):
        """Context manager: auth client whose recording service raises SENTINEL."""
        from contextlib import contextmanager

        from api.canvas_recording_routes import router

        @contextmanager
        def _cm():
            service = MagicMock()
            for method in (
                "start_recording", "record_event", "stop_recording",
                "get_recording", "list_recordings",
            ):
                setattr(service, method, AsyncMock(side_effect=RuntimeError(SENTINEL)))
            with patch(
                "api.canvas_recording_routes.get_canvas_recording_service",
                return_value=service,
            ):
                yield make_client(router)

        return _cm()

    def test_start_recording_no_leak(self):
        with self._client_with_raising_service() as client:
            resp = client.post(
                "/api/canvas/recording/start",
                json={"agent_id": "a-1", "reason": "test"},
            )
        assert resp.status_code == 500
        assert SENTINEL not in resp.text

    def test_record_event_no_leak(self):
        with self._client_with_raising_service() as client:
            resp = client.post(
                "/api/canvas/recording/r-1/event",
                json={"event_type": "update", "event_data": {}},
            )
        assert resp.status_code == 500
        assert SENTINEL not in resp.text

    def test_stop_recording_no_leak(self):
        with self._client_with_raising_service() as client:
            resp = client.post(
                "/api/canvas/recording/r-1/stop", json={}
            )
        assert resp.status_code == 500
        assert SENTINEL not in resp.text

    def test_get_recording_no_leak(self):
        with self._client_with_raising_service() as client:
            resp = client.get("/api/canvas/recording/r-1")
        assert resp.status_code == 500
        assert SENTINEL not in resp.text

    def test_list_recordings_no_leak(self):
        with self._client_with_raising_service() as client:
            resp = client.get("/api/canvas/recording")
        assert resp.status_code == 500
        assert SENTINEL not in resp.text


# ============================================================================
# B. Social media — platform_results + 500-details leaks
# ============================================================================

class TestSocialMediaLeaks:
    def _client(self, db=None):
        from api.social_media_routes import router
        return make_client(router, db=db)

    def test_platform_results_no_leak(self):
        """A poster raising must not surface str(e) in platform_results."""
        async def _boom(**kwargs):
            raise RuntimeError(SENTINEL)

        db = MagicMock()
        db.query.return_value.filter.return_value.count.return_value = 0
        with patch("api.social_media_routes.PLATFORM_POSTERS", {"twitter": _boom}):
            resp = self._client(db=db).post(
                "/api/v1/social/post",
                json={"platforms": ["twitter"], "text": "hello"},
            )
        assert resp.status_code == 200
        assert SENTINEL not in resp.text

    def test_successful_post_returns_200(self):
        """Happy path: a successful poster must return 200 with a post_id.
        (Regression: line 656 called uuid.uuid4() with only uuid4 imported —
        every successful post 500'd AFTER the platform post was already sent.)"""
        async def _ok(**kwargs):
            return {"success": True, "post_id": "post-1"}

        db = MagicMock()
        db.query.return_value.filter.return_value.count.return_value = 0
        with patch("api.social_media_routes.PLATFORM_POSTERS", {"twitter": _ok}):
            resp = self._client(db=db).post(
                "/api/v1/social/post",
                json={"platforms": ["twitter"], "text": "hello"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["post_id"]

    def test_connected_accounts_returns_200(self):
        """GET /connected-accounts must not crash on the token lookup.
        (Regression: it queried OAuthToken.provider/status — columns that do
        not exist — so every request 500'd with AttributeError.)"""
        from datetime import datetime, timezone

        fake_token = MagicMock()
        fake_token.provider = "twitter"
        fake_token.id = "t-1"
        fake_token.scope = "tweet.read tweet.write"
        fake_token.updated_at = datetime(2026, 7, 31, tzinfo=timezone.utc)

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [fake_token]
        resp = self._client(db=db).get("/api/v1/social/connected-accounts")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["accounts"][0]["platform"] == "twitter"
        assert body["accounts"][0]["scopes"] == "tweet.read tweet.write"

    def test_500_details_no_leak(self):
        """Unexpected failures must not leak str(e) via response details."""
        db = MagicMock()
        db.query.side_effect = RuntimeError(SENTINEL)
        resp = self._client(db=db).post(
            "/api/v1/social/post",
            json={"platforms": ["twitter"], "text": "hello"},
        )
        assert resp.status_code == 500
        assert SENTINEL not in resp.text


# ============================================================================
# C. Admin — bulk-resolve errors list
# ============================================================================

class TestAdminBulkResolveLeaks:
    def test_bulk_resolve_no_leak(self):
        from api.admin_routes import router
        service = MagicMock()
        service.resolve_conflict.side_effect = RuntimeError(SENTINEL)
        with patch(
            "core.conflict_resolution_service.ConflictResolutionService",
            return_value=service,
        ):
            resp = make_client(router).post(
                "/api/admin/conflicts/bulk-resolve",
                json={
                    "conflict_ids": [1, 2],
                    "strategy": "remote_wins",
                    "resolved_by": "u-1",
                },
            )
        assert resp.status_code == 200
        assert SENTINEL not in resp.text

    def test_bulk_resolve_keeps_generic_errors(self):
        """Errors stay client-visible but must be generic."""
        from api.admin_routes import router
        service = MagicMock()
        service.resolve_conflict.side_effect = RuntimeError("secret db detail")
        with patch(
            "core.conflict_resolution_service.ConflictResolutionService",
            return_value=service,
        ):
            resp = make_client(router).post(
                "/api/admin/conflicts/bulk-resolve",
                json={
                    "conflict_ids": [7],
                    "strategy": "remote_wins",
                    "resolved_by": "u-1",
                },
            )
        assert resp.status_code == 200
        body = resp.text
        assert "Failed to resolve" in body
        assert "secret db detail" not in body
