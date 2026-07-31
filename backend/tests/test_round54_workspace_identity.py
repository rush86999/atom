"""
Round 54 — Workspace routes: cross-user access + attribution spoofing + str(e)
(Red-Green-Refactor).

api/workspace_routes.py (mounted at /api/v1/workspaces) trusts client-supplied
identity and skips ownership checks on every endpoint:

  A. POST /unified — create_unified_workspace(user_id=request.user_id):
     creates a workspace OWNED BY any user_id the client supplies
     (attribution spoofing).
  B. GET /unified?user_id=X — list filters by the client-supplied user_id:
     cross-user workspace read (names, platform configs, sync state).
  C. GET /unified/{id}, POST /unified/{id}/platforms,
     POST /unified/{id}/sync (propagates changes to EXTERNAL platforms!),
     DELETE /unified/{id} — no ownership check: any user can read/modify/
     delete ANY user's workspace and trigger cross-platform side effects.
  D. 5 sites leak str(e) in details={"error": str(e)} (R41 class).

Fix: token identity for create/list; ownership checks on all workspace-id
endpoints; generic error details.
"""

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user as auth_get_current_user
from core.database import get_db

SECRET = "secret-workspace-internal-xyz"


def make_client(user_id="u-54"):
    from api.workspace_routes import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[auth_get_current_user] = lambda: MagicMock(
        id=user_id, email="u@example.com"
    )
    app.dependency_overrides[get_db] = lambda: MagicMock()
    return TestClient(app, raise_server_exceptions=False)


def _owned_workspace(user_id, ws_id="ws-1"):
    ws = MagicMock()
    ws.id = ws_id
    ws.user_id = user_id
    ws.name = "Team Space"
    ws.description = "d"
    ws.slack_workspace_id = None
    ws.discord_guild_id = None
    ws.google_chat_space_id = None
    ws.teams_team_id = None
    ws.sync_status = "synced"
    ws.last_sync_at = None
    ws.platform_count = 0
    ws.member_count = 0
    ws.created_at = None
    ws.updated_at = None
    return ws


class TestWorkspaceIdentity:
    def test_create_uses_token_identity_not_spoofed_user_id(self):
        client = make_client(user_id="u-54")

        import api.workspace_routes as mod

        with patch.object(
            mod.WorkspaceSyncService, "create_unified_workspace"
        ) as create, patch(
            "api.workspace_routes._workspace_to_dict",
            return_value={},
        ):
            resp = client.post(
                "/api/v1/workspaces/unified",
                json={
                    "user_id": "victim-999",
                    "name": "Sneaky Space",
                    "slack_workspace_id": "T123",
                },
            )

        assert resp.status_code == 200
        create.assert_called_once()
        kwargs = create.call_args.kwargs
        assert kwargs.get("user_id") == "u-54", (
            "create_unified_workspace was called with the client-supplied "
            f"user_id {kwargs.get('user_id')!r} instead of the token identity"
        )

    def test_list_filter_uses_current_user(self):
        import api.workspace_routes as mod

        # Rebuild with a recorder db to capture the filter expression.
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(mod.router)
        app.dependency_overrides[auth_get_current_user] = lambda: MagicMock(
            id="u-54", email="u@example.com"
        )
        db = MagicMock()
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)

        # order_by(...).all() must yield a list
        db.query.return_value.order_by.return_value.all.return_value = []
        resp = client.get("/api/v1/workspaces/unified?user_id=victim-999")

        assert resp.status_code == 200
        filter_call = db.query.return_value.filter.call_args
        assert filter_call is not None, "list must filter workspaces"
        expr = filter_call[0][0]
        # BinaryExpression: UnifiedWorkspace.user_id == <value>
        assert expr.right.value == "u-54", (
            f"list filtered by the client-supplied user_id ({expr.right.value!r}) "
            "instead of the token identity"
        )

    def test_get_status_denies_other_users_workspace(self):
        other = _owned_workspace("victim-999")

        import api.workspace_routes as mod

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = other

        app = FastAPI()
        app.include_router(mod.router)
        app.dependency_overrides[auth_get_current_user] = lambda: MagicMock(
            id="u-54", email="u@example.com"
        )
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)

        with patch.object(mod.WorkspaceSyncService, "get_workspace_sync_status") as status:
            resp = client.get("/api/v1/workspaces/unified/ws-1")

        assert resp.status_code == 403, (
            "get_status exposed another user's workspace sync state"
        )
        status.assert_not_called()

    def test_delete_denies_other_users_workspace(self):
        client = make_client(user_id="u-54")
        other = _owned_workspace("victim-999")

        from core.models import UnifiedWorkspace

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = other
        import api.workspace_routes as mod

        app = FastAPI()
        app.include_router(mod.router)
        app.dependency_overrides[auth_get_current_user] = lambda: MagicMock(
            id="u-54", email="u@example.com"
        )
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.delete("/api/v1/workspaces/unified/ws-1")

        assert resp.status_code == 403, (
            "delete allowed a cross-user workspace deletion"
        )
        db.delete.assert_not_called()

    def test_sync_denies_other_users_workspace(self):
        """propagate_change writes to EXTERNAL platforms — must be owner-only."""
        client = make_client(user_id="u-54")
        other = _owned_workspace("victim-999")

        from core.models import UnifiedWorkspace

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = other
        import api.workspace_routes as mod

        app = FastAPI()
        app.include_router(mod.router)
        app.dependency_overrides[auth_get_current_user] = lambda: MagicMock(
            id="u-54", email="u@example.com"
        )
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)

        with patch.object(mod.WorkspaceSyncService, "propagate_change") as prop:
            resp = client.post(
                "/api/v1/workspaces/unified/ws-1/sync",
                json={
                    "workspace_id": "ws-1",
                    "source_platform": "slack",
                    "change_type": "message",
                    "change_data": {"text": "hi"},
                },
            )

        assert resp.status_code == 403
        prop.assert_not_called()

    def test_create_error_does_not_leak(self):
        client = make_client(user_id="u-54")

        import api.workspace_routes as mod

        with patch.object(
            mod.WorkspaceSyncService,
            "create_unified_workspace",
            side_effect=RuntimeError(SECRET),
        ):
            resp = client.post(
                "/api/v1/workspaces/unified",
                json={"user_id": "u-54", "name": "X", "slack_workspace_id": "T123"},
            )

        assert resp.status_code == 500
        assert SECRET not in resp.text, (
            f"create endpoint leaks internal exception detail: {resp.text[:200]!r}"
        )

    def test_pricing_estimate_does_not_leak(self):
        """POST /api/ai/pricing/estimate must not leak exception strings."""
        from api.byok_routes import router as byok_router

        app = FastAPI()
        app.include_router(byok_router)
        app.dependency_overrides[auth_get_current_user] = lambda: MagicMock(
            id="u-54", email="u@example.com"
        )
        app.dependency_overrides[get_db] = lambda: MagicMock()
        client = TestClient(app, raise_server_exceptions=False)

        with patch(
            "core.dynamic_pricing_fetcher.get_pricing_fetcher",
            side_effect=RuntimeError(SECRET),
        ):
            resp = client.post(
                "/api/ai/pricing/estimate",
                json={"model": "gpt-4o", "input_tokens": 10, "output_tokens": 10},
            )

        assert resp.status_code == 200  # ApiResponse-style failure envelope
        assert SECRET not in resp.text, (
            f"pricing estimate leaks internal exception detail: {resp.text[:200]!r}"
        )
