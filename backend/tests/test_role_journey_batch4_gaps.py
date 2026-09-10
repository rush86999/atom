# -*- coding: utf-8 -*-
"""Role-journey gap closure, batch 4 (2026-09-09).

Re-traced every role's journey after the GoalRun / HITL-notify / LLM-spend
features landed and locked the gaps found:

1.  WebSocket channel subscriptions are ACL'd: ``user:{id}`` personal
    channels (canvas presents, office snapshots) are owner-only — any
    authenticated client could previously subscribe to ANY user's channel
    and watch their live canvas traffic.
2.  /api/chat/routing-stats (installation-wide model telemetry) is
    workspace_admin+, matching the rest of the LLM spend band.
3.  User-activity heartbeats/overrides/sessions are owner-scoped (was: any
    authenticated user could forge presence, read other users' session
    TOKENS, and kill their sessions).
4.  USER_VIEW / USER_MANAGE are enforced permissions now (workspace
    directory read + enterprise user mutations) — the journey tripwire's
    last documented granted-but-unenforced pair.
5.  The self-directed training queue is tenant-scoped.

Gate-only assertions use ``!= 403`` for allowed bands: the subject is the
gate; the handler behind it may legitimately 4xx on the mock db.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from core.auth import get_current_user as auth_get_current_user
from core.database import get_db
from core.models import UserRole
from core.security.rbac import role_level


def _user_mock(user_id="u-1", role="member"):
    u = MagicMock()
    u.id = user_id
    u.role = role
    u.email = f"{user_id}@example.com"
    return u


def make_role_client(router, role, user_id="u-1"):
    """TestClient whose User row carries `role` (round-65 pattern: gates
    re-read the user from the db; here the mock db returns the same user
    for every query)."""
    app = FastAPI()
    app.include_router(router)
    db = MagicMock()
    db_user = _user_mock(user_id=user_id, role=role)
    db.query.return_value.filter.return_value.first.return_value = db_user
    app.dependency_overrides[auth_get_current_user] = lambda: db_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False), db


# ============================================================================
# 1. WebSocket channel ACL
# ============================================================================


class TestWebSocketChannelACL:
    def test_own_user_channel_allowed(self):
        from api.websocket_routes import channel_allowed_for_user

        assert channel_allowed_for_user("user:u-1", "u-1") is True

    def test_own_session_channel_allowed(self):
        from api.websocket_routes import channel_allowed_for_user

        assert channel_allowed_for_user("user:u-1:session:s-9", "u-1") is True

    def test_other_users_channel_denied(self):
        from api.websocket_routes import channel_allowed_for_user

        assert channel_allowed_for_user("user:u-2", "u-1") is False

    def test_other_users_session_channel_denied(self):
        from api.websocket_routes import channel_allowed_for_user

        assert channel_allowed_for_user("user:u-2:session:s-9", "u-1") is False

    def test_user_prefix_without_id_denied(self):
        from api.websocket_routes import channel_allowed_for_user

        assert channel_allowed_for_user("user:", "u-1") is False
        assert channel_allowed_for_user("user:", "") is False

    @pytest.mark.parametrize(
        "channel",
        ["workspace:default", "team:team-1", "agent:123", "projects", ""],
    )
    def test_shared_channels_stay_open(self, channel):
        """Shared-surface channels are multi-consumer by design — the ACL
        must not break team chat, agent feeds or project comments."""
        from api.websocket_routes import channel_allowed_for_user

        if channel == "":
            assert channel_allowed_for_user(channel, "u-1") is False
        else:
            assert channel_allowed_for_user(channel, "u-1") is True

    def test_integer_user_id_string_compares(self):
        from api.websocket_routes import channel_allowed_for_user

        assert channel_allowed_for_user("user:7", 7) is True
        assert channel_allowed_for_user("user:8", 7) is False


# ============================================================================
# 2. routing-stats gate (workspace_admin+ — installation-wide telemetry)
# ============================================================================


class TestRoutingStatsGate:
    def _route(self):
        from integrations.chat_routes import router

        for route in router.routes:
            if getattr(route, "path", "") == "/api/chat/routing-stats":
                return route
        pytest.fail("routing-stats route not found on the chat router")

    def _checker(self):
        # The role gate is a Depends(require_role(...)) sub-dependency.
        for dep in self._route().dependant.dependencies:
            call = dep.call
            if call.__name__ == "role_checker":
                return call
        pytest.fail("routing-stats has no require_role dependency")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "role", ["member", "team_lead", "guest", "viewer"]
    )
    async def test_below_workspace_admin_denied(self, role):
        checker = self._checker()
        with pytest.raises(HTTPException) as exc:
            await checker(_user_mock(role=role))
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "role",
        ["workspace_admin", "admin", "owner", "super_admin"],
    )
    async def test_workspace_admin_band_allowed(self, role):
        checker = self._checker()
        user = _user_mock(role=role)
        assert await checker(user) is user


# ============================================================================
# 3. User-activity ownership (presence forgery + session tokens)
# ============================================================================


class TestUserActivityOwnership:
    @pytest.fixture()
    def client(self):
        from api.user_activity_routes import router

        app = FastAPI()
        app.include_router(router)
        db = MagicMock()
        db_user = _user_mock(user_id="u-1", role="member")
        app.dependency_overrides[auth_get_current_user] = lambda: db_user
        app.dependency_overrides[get_db] = lambda: db
        return TestClient(app, raise_server_exceptions=False), db, db_user

    def test_cannot_heartbeat_for_another_user(self, client):
        tc, _, _ = client
        with patch("api.user_activity_routes.UserActivityService"):
            resp = tc.post(
                "/api/users/u-OTHER/activity/heartbeat",
                json={"session_token": "tok"},
            )
        assert resp.status_code == 403, "any user could forge another's presence"

    def test_own_heartbeat_passes_the_gate(self, client):
        tc, _, _ = client
        with patch("api.user_activity_routes.UserActivityService") as svc:
            svc.return_value.record_heartbeat = AsyncMock(
                return_value=MagicMock(
                    user_id="u-1", state=MagicMock(value="online"),
                    last_activity_at=MagicMock(
                        isoformat=lambda: "2026-09-09T00:00:00"
                    ),
                    manual_override=False, manual_override_expires_at=None,
                )
            )
            resp = tc.post(
                "/api/users/u-1/activity/heartbeat",
                json={"session_token": "tok"},
            )
        assert resp.status_code != 403, resp.text

    def test_cannot_override_another_users_state(self, client):
        tc, _, _ = client
        with patch("api.user_activity_routes.UserActivityService"):
            resp = tc.post(
                "/api/users/u-OTHER/activity/override",
                json={"state": "offline"},
            )
            resp2 = tc.delete("/api/users/u-OTHER/activity/override")
        assert resp.status_code == 403
        assert resp2.status_code == 403

    def test_cannot_read_another_users_sessions(self, client):
        """Session rows carry bearer tokens — cross-user reads are a
        credential leak, not just a presence question."""
        tc, _, _ = client
        with patch("api.user_activity_routes.UserActivityService"):
            resp = tc.get("/api/users/u-OTHER/activity/sessions")
        assert resp.status_code == 403

    def test_terminate_other_users_session_member_denied(self, client):
        tc, db, _ = client
        victim_session = MagicMock()
        victim_session.user_id = "u-OTHER"
        db.query.return_value.filter.return_value.first.return_value = victim_session
        with patch("api.user_activity_routes.UserActivityService"):
            resp = tc.delete("/api/users/activity/sessions/tok-of-other")
        assert resp.status_code == 403

    def test_terminate_own_session_passes_the_gate(self, client):
        tc, db, _ = client
        own_session = MagicMock()
        own_session.user_id = "u-1"
        db.query.return_value.filter.return_value.first.return_value = own_session
        with patch("api.user_activity_routes.UserActivityService") as svc:
            svc.return_value.terminate_session = AsyncMock(return_value=True)
            resp = tc.delete("/api/users/activity/sessions/my-token")
        assert resp.status_code != 403, resp.text

    def test_terminate_unknown_session_404(self, client):
        tc, db, _ = client
        db.query.return_value.filter.return_value.first.return_value = None
        resp = tc.delete("/api/users/activity/sessions/nope")
        assert resp.status_code == 404

    def test_supervisor_may_terminate_a_session(self):
        from api.user_activity_routes import router

        app = FastAPI()
        app.include_router(router)
        db = MagicMock()
        victim_session = MagicMock()
        victim_session.user_id = "u-OTHER"
        db.query.return_value.filter.return_value.first.return_value = victim_session
        lead = _user_mock(user_id="lead-1", role="team_lead")
        app.dependency_overrides[auth_get_current_user] = lambda: lead
        app.dependency_overrides[get_db] = lambda: db
        tc = TestClient(app, raise_server_exceptions=False)
        with patch("api.user_activity_routes.UserActivityService") as svc:
            svc.return_value.terminate_session = AsyncMock(return_value=True)
            resp = tc.delete("/api/users/activity/sessions/tok")
        assert resp.status_code != 403, resp.text


class TestAvailableSupervisorsPermission:
    """USER_VIEW enforcement: the workspace directory read (viewer+)."""

    def test_guest_denied(self):
        from api.user_activity_routes import router

        client, _ = make_role_client(router, "guest")
        with patch("api.user_activity_routes.UserActivityService") as svc:
            svc.return_value.get_available_supervisors = AsyncMock(return_value=[])
            resp = client.get("/api/users/available-supervisors")
        assert resp.status_code == 403

    @pytest.mark.parametrize("role", ["viewer", "member", "team_lead", "owner"])
    def test_viewer_and_above_allowed(self, role):
        from api.user_activity_routes import router

        client, _ = make_role_client(router, role)
        with patch("api.user_activity_routes.UserActivityService") as svc:
            svc.return_value.get_available_supervisors = AsyncMock(return_value=[])
            resp = client.get("/api/users/available-supervisors")
        assert resp.status_code != 403, resp.text


# ============================================================================
# 4. USER_MANAGE on the enterprise user mutations
# ============================================================================


class TestEnterpriseUserManagePermission:
    """user:manage per the permission matrix: workspace_admin+/owner (a
    plain domain `admin` deliberately does NOT provision accounts — it is
    not in USER_MANAGE's grant list). The router-level workspace_admin+
    hierarchy gate stays as defense in depth."""

    @pytest.mark.parametrize("method,path,kw", [
        ("POST", "/api/enterprise/users", {"json": {}}),
        ("PATCH", "/api/enterprise/users/some-id", {"json": {"role": "member"}}),
        ("DELETE", "/api/enterprise/users/some-id", {}),
    ])
    @pytest.mark.parametrize("role", ["member", "team_lead", "admin"])
    def test_below_user_manage_denied(self, method, path, kw, role):
        from core.enterprise_user_management import router

        client, _ = make_role_client(router, role)
        resp = client.request(method, path, **kw)
        assert resp.status_code == 403, (
            f"{role} must not reach {method} {path} (user:manage)"
        )

    @pytest.mark.parametrize("method,path,kw", [
        ("POST", "/api/enterprise/users", {"json": {}}),
        ("PATCH", "/api/enterprise/users/some-id", {"json": {"role": "member"}}),
        ("DELETE", "/api/enterprise/users/some-id", {}),
    ])
    @pytest.mark.parametrize("role", ["workspace_admin", "owner", "super_admin"])
    def test_user_manage_band_allowed(self, method, path, kw, role):
        from core.enterprise_user_management import router

        client, _ = make_role_client(router, role)
        resp = client.request(method, path, **kw)
        assert resp.status_code != 403, (
            f"{role} holds user:manage but was denied {method} {path}: {resp.text}"
        )


# ============================================================================
# 5. Self-directed training queue tenant scoping
# ============================================================================


class TestSelfDirectedTenantScoping:
    @pytest.mark.asyncio
    async def test_queue_is_tenant_scoped(self):
        from api.agent_maturity_routes import self_directed_progress_queue

        user = _user_mock(user_id="u-1", role="team_lead")
        user.tenant_id = "tenant-A"
        db = MagicMock()
        with patch(
            "core.self_directed_progress.student_agents", return_value=[]
        ) as sa, patch(
            "core.self_directed_progress.snapshot", side_effect=lambda db, a: {}
        ):
            resp = await self_directed_progress_queue(
                agent_id=None, current_user=user, db=db
            )
        assert sa.call_args.kwargs.get("tenant_id") == "tenant-A", (
            "the STUDENT queue must be scoped to the caller's tenant"
        )
        assert resp == {"agents": [], "count": 0}


# ============================================================================
# 6. Tripwire contract: USER_VIEW / USER_MANAGE stay enforced
# ============================================================================


class TestTripwireContract:
    def test_no_unenforced_permissions_remain_listed(self):
        from tests.e2e_ui.tests.test_journey_permission_matrix import (
            PERMISSION_ENDPOINTS,
            UNENFORCED_PERMISSIONS,
        )
        from core.rbac_service import Permission

        assert UNENFORCED_PERMISSIONS == []
        enforced = {p for p, *_ in PERMISSION_ENDPOINTS}
        assert Permission.USER_VIEW in enforced
        assert Permission.USER_MANAGE in enforced

    def test_role_levels_importable_and_monotonic(self):
        assert role_level(UserRole.GUEST) < role_level(UserRole.OWNER)
