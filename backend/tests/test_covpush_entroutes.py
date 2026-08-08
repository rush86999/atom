"""
Coverage-push tests for enterprise_auth_endpoints, workflow_debugging,
and social_media_routes (TDD bug-hunt round).

Real bugs found are asserted with failing tests first, then minimal fixes
in the route modules. Everything else is exhaustive happy/error-path coverage
via TestClient with dependency overrides.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

os.environ.setdefault("BYPASS_RATE_LIMIT", "1")
os.environ.setdefault("ENTERPRISE_JWT_SECRET", "test-enterprise-jwt-secret")

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.auth import get_current_user
from core.base_routes import atom_exception_handler
from core.database import get_db
from core.enterprise_auth_service import EnterpriseAuthService, UserCredentials
from core.models import (
    Base,
    DebugVariable,
    ExecutionTrace,
    IntegrationToken,
    SocialMediaAudit,
    SocialPostHistory,
    Tenant,
    User,
    WorkflowBreakpoint,
    WorkflowDebugSession,
    Workspace,
)

from api.enterprise_auth_endpoints import (
    ChangePasswordRequest,
    UserLogin,
    UserRegister,
    _verify_enterprise_credentials,
    _verify_enterprise_credentials_new,
    require_permission,
    require_role,
    router as auth_router,
)
from api.social_media_routes import (
    PLATFORM_POSTERS,
    PlatformConfig,
    SocialPostRequest,
    post_to_facebook,
    post_to_linkedin,
    post_to_twitter,
    router as social_router,
)
from api.workflow_debugging import router as wf_debug_router

PASSWORD = "SecurePass123!"
USER_ID = str(uuid.uuid4())


# ============================================================================
# Shared database / app fixtures
# ============================================================================

_CLEAN_TABLES = (
    "debug_variables",
    "execution_traces",
    "workflow_breakpoints",
    "workflow_debug_sessions",
    "social_media_audit",
    "social_post_history",
    "integration_tokens",
    "user_workspaces",
    "workspaces",
    "tenants",
    "users",
)


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture(scope="function")
def db(engine):
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def _clean_tables(db):
    yield
    db.rollback()
    for table in _CLEAN_TABLES:
        db.execute(text(f"DELETE FROM {table}"))
    db.commit()


@pytest.fixture(scope="function")
def app(db):
    app = FastAPI()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.add_exception_handler(HTTPException, atom_exception_handler)
    app.include_router(auth_router)
    app.include_router(wf_debug_router)
    app.include_router(social_router)
    yield app
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(app):
    return TestClient(app)


@pytest.fixture(scope="function")
def auth_user(db):
    user = User(
        id=USER_ID,
        email="alice@example.com",
        first_name="Alice",
        last_name="A",
        role="member",
        status="active",
        hashed_password=EnterpriseAuthService().hash_password(PASSWORD),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture(scope="function")
def access_token():
    return EnterpriseAuthService().create_access_token(USER_ID)


@pytest.fixture(scope="function")
def refresh_token():
    return EnterpriseAuthService().create_refresh_token(USER_ID)


@pytest.fixture(scope="function")
def auth_user_client(client, auth_user):
    def override_get_current_user():
        return auth_user

    client.app.dependency_overrides[get_current_user] = override_get_current_user
    yield client
    client.app.dependency_overrides.pop(get_current_user, None)


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# Enterprise auth endpoints
# ============================================================================


class TestRegister:
    def test_register_success(self, client, db):
        resp = client.post("/api/auth/register", json={
            "email": "new@example.com",
            "password": PASSWORD,
            "first_name": "New",
            "last_name": "User",
            "role": "member",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        user = db.query(User).filter(User.email == "new@example.com").first()
        assert user is not None
        assert user.hashed_password != PASSWORD
        assert user.tenant_id is not None
        assert user.workspace_id is not None
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        assert tenant is not None
        workspace = db.query(Workspace).filter(Workspace.id == user.workspace_id).first()
        assert workspace is not None

    def test_register_duplicate_email(self, client, auth_user):
        resp = client.post("/api/auth/register", json={
            "email": auth_user.email,
            "password": PASSWORD,
            "first_name": "Dup",
            "last_name": "User",
        })
        assert resp.status_code == 409
        assert resp.json()["success"] is False

    def test_register_weak_password_422(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "weak@example.com",
            "password": "short",
            "first_name": "W",
            "last_name": "U",
        })
        assert resp.status_code == 422

    def test_register_invalid_email_422(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "not-an-email",
            "password": PASSWORD,
            "first_name": "W",
            "last_name": "U",
        })
        assert resp.status_code == 422

    def test_register_integrity_error_race_conflict(self, client, auth_user, db):
        real_commit = db.commit
        calls = {"n": 0}

        def flaky_commit():
            calls["n"] += 1
            if calls["n"] == 1:
                raise IntegrityError("stmt", {}, Exception("unique violation"))
            real_commit()

        db.commit = flaky_commit
        try:
            resp = client.post("/api/auth/register", json={
                "email": "race@example.com",
                "password": PASSWORD,
                "first_name": "R",
                "last_name": "C",
            })
            assert resp.status_code == 409
        finally:
            db.commit = real_commit

    def test_register_internal_error_500(self, client):
        with patch(
            "core.enterprise_auth_service.EnterpriseAuthService.hash_password",
            side_effect=RuntimeError("boom"),
        ):
            resp = client.post("/api/auth/register", json={
                "email": "err@example.com",
                "password": PASSWORD,
                "first_name": "E",
                "last_name": "R",
            })
        assert resp.status_code == 500
        assert resp.json()["success"] is False

    def test_register_tenant_creation_failure_still_succeeds(self, client, db):
        with patch(
            "core.models.Tenant",
            side_effect=RuntimeError("tenant setup failed"),
        ):
            resp = client.post("/api/auth/register", json={
                "email": "notenant@example.com",
                "password": PASSWORD,
                "first_name": "T",
                "last_name": "N",
            })
        assert resp.status_code == 201
        user = db.query(User).filter(User.email == "notenant@example.com").first()
        assert user is not None
        assert user.tenant_id is None

    def test_user_register_model_validation(self):
        with pytest.raises(Exception):
            UserRegister(email="x", password="short", first_name="", last_name="")


class TestLogin:
    CREDS = {
        "user_id": USER_ID,
        "username": "alice@example.com",
        "email": "alice@example.com",
        "roles": ["member"],
        "security_level": "standard",
        "permissions": [],
    }

    def test_login_success(self, client, auth_user):
        with patch(
            "api.enterprise_auth_endpoints._verify_enterprise_credentials",
            new=AsyncMock(return_value=self.CREDS),
        ):
            resp = client.post("/api/auth/login", json={
                "username": "alice@example.com",
                "password": PASSWORD,
            })
        assert resp.status_code == 200
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert body["user_id"] == USER_ID
        assert body["roles"] == ["member"]
        assert auth_user.last_login is not None

    def test_login_invalid_credentials_401(self, client):
        with patch(
            "api.enterprise_auth_endpoints._verify_enterprise_credentials",
            new=AsyncMock(return_value=None),
        ):
            resp = client.post("/api/auth/login", json={
                "username": "alice@example.com",
                "password": "wrong-password",
            })
        assert resp.status_code == 401
        assert resp.json()["success"] is False

    def test_login_internal_error_500(self, client):
        with patch(
            "api.enterprise_auth_endpoints._verify_enterprise_credentials",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            resp = client.post("/api/auth/login", json={
                "username": "alice@example.com",
                "password": PASSWORD,
            })
        assert resp.status_code == 500

    def test_login_user_model_validation(self):
        assert UserLogin(username="u", password="p").password == "p"
        with pytest.raises(Exception):
            UserLogin(username="u", password="x" * 129)


class TestRefresh:
    def test_refresh_success_rotates_token(self, client, auth_user, refresh_token):
        with patch(
            "core.enterprise_auth_service.EnterpriseAuthService.verify_credentials",
            return_value=UserCredentials(
                user_id=USER_ID,
                username="alice@example.com",
                email="alice@example.com",
                roles=["member"],
                security_level="standard",
                permissions=["all"],
                mfa_enabled=False,
            ),
        ):
            resp = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == USER_ID
        assert body["refresh_token"] != refresh_token
        assert body["access_token"]

    def test_refresh_success_fallback_credentials(self, client, auth_user, refresh_token):
        resp = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        assert resp.json()["user_id"] == USER_ID

    def test_refresh_invalid_token_401(self, client):
        resp = client.post("/api/auth/refresh", json={"refresh_token": "garbage.token.here"})
        assert resp.status_code == 401

    def test_refresh_wrong_token_type_401(self, client, access_token):
        resp = client.post("/api/auth/refresh", json={"refresh_token": access_token})
        assert resp.status_code == 401

    def test_refresh_user_not_found_401(self, client, refresh_token):
        resp = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 401

    def test_refresh_internal_error_401(self, client, auth_user, refresh_token):
        with patch(
            "core.enterprise_auth_service.EnterpriseAuthService.create_access_token",
            side_effect=RuntimeError("boom"),
        ):
            resp = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 401
        assert resp.json()["success"] is False

    def test_refresh_missing_body_422(self, client):
        resp = client.post("/api/auth/refresh", json={})
        assert resp.status_code == 422


class TestMe:
    def test_me_success(self, client, auth_user, access_token):
        resp = client.get("/api/auth/me", headers=_auth_headers(access_token))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["email"] == auth_user.email
        assert data["user_id"] == USER_ID

    def test_me_invalid_token_401(self, client):
        resp = client.get("/api/auth/me", headers=_auth_headers("not-a-token"))
        assert resp.status_code == 401

    def test_me_missing_token_401(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_user_not_found_404(self, client, access_token):
        resp = client.get("/api/auth/me", headers=_auth_headers(access_token))
        assert resp.status_code == 404

    def test_me_internal_error_500(self, client, auth_user, access_token):
        with patch(
            "core.enterprise_auth_service.EnterpriseAuthService.verify_token",
            side_effect=RuntimeError("boom"),
        ):
            resp = client.get("/api/auth/me", headers=_auth_headers(access_token))
        assert resp.status_code == 500


class TestChangePassword:
    def test_change_password_success(self, client, auth_user, access_token):
        resp = client.post(
            "/api/auth/change-password",
            json={"old_password": PASSWORD, "new_password": "NewPass456!"},
            headers=_auth_headers(access_token),
        )
        assert resp.status_code == 200
        assert EnterpriseAuthService().verify_password(
            "NewPass456!", auth_user.hashed_password
        )

    def test_change_password_invalid_token_401(self, client):
        resp = client.post(
            "/api/auth/change-password",
            json={"old_password": PASSWORD, "new_password": "NewPass456!"},
            headers=_auth_headers("garbage"),
        )
        assert resp.status_code == 401

    def test_change_password_user_not_found_404(self, client, access_token):
        resp = client.post(
            "/api/auth/change-password",
            json={"old_password": PASSWORD, "new_password": "NewPass456!"},
            headers=_auth_headers(access_token),
        )
        assert resp.status_code == 404

    def test_change_password_locked_account_401(self, client, auth_user, db, access_token):
        user = db.query(User).filter(User.id == USER_ID).first()
        user.status = "locked"
        db.commit()
        resp = client.post(
            "/api/auth/change-password",
            json={"old_password": PASSWORD, "new_password": "NewPass456!"},
            headers=_auth_headers(access_token),
        )
        assert resp.status_code == 401

    def test_change_password_wrong_old_password_401(self, client, auth_user, access_token):
        resp = client.post(
            "/api/auth/change-password",
            json={"old_password": "WrongOldPass!", "new_password": "NewPass456!"},
            headers=_auth_headers(access_token),
        )
        assert resp.status_code == 401

    def test_change_password_internal_error_500(self, client, auth_user, access_token):
        with patch(
            "core.enterprise_auth_service.EnterpriseAuthService.hash_password",
            side_effect=RuntimeError("boom"),
        ):
            resp = client.post(
                "/api/auth/change-password",
                json={"old_password": PASSWORD, "new_password": "NewPass456!"},
                headers=_auth_headers(access_token),
            )
        assert resp.status_code == 500

    def test_change_password_weak_new_password_422(self, client, auth_user, access_token):
        resp = client.post(
            "/api/auth/change-password",
            json={"old_password": PASSWORD, "new_password": "short"},
            headers=_auth_headers(access_token),
        )
        assert resp.status_code == 422

    def test_change_password_model_validation(self):
        with pytest.raises(Exception):
            ChangePasswordRequest(old_password="x" * 129, new_password="ok123456")


class TestTestAuthAndDeps:
    def test_test_auth_success(self, client, auth_user, access_token):
        resp = client.get("/api/auth/test-auth", headers=_auth_headers(access_token))
        assert resp.status_code == 200
        assert resp.json()["user"]["user_id"] == USER_ID

    def test_test_auth_invalid_token_401(self, client):
        resp = client.get("/api/auth/test-auth", headers=_auth_headers("bad.token.value"))
        assert resp.status_code == 401

    async def test_require_role_allowed(self):
        @require_role(["admin", "member"])
        async def handler(current_user):
            return current_user

        result = await handler(current_user={"roles": ["member"]})
        assert result["roles"] == ["member"]

    async def test_require_role_denied(self):
        @require_role(["admin"])
        async def handler(current_user):
            return current_user

        with pytest.raises(Exception):
            await handler(current_user={"roles": ["member"]})

    async def test_require_permission_all_wildcard(self):
        @require_permission("social_media_post")
        async def handler(current_user):
            return current_user

        result = await handler(current_user={"permissions": ["all"]})
        assert result["permissions"] == ["all"]

    async def test_require_permission_granted(self):
        @require_permission("social_media_post")
        async def handler(current_user):
            return current_user

        result = await handler(current_user={"permissions": ["social_media_post"]})
        assert result["permissions"] == ["social_media_post"]

    async def test_require_permission_denied(self):
        @require_permission("admin_panel")
        async def handler(current_user):
            return current_user

        with pytest.raises(Exception):
            await handler(current_user={"permissions": ["social_media_post"]})


class TestVerifyEnterpriseCredentialsHelpers:
    @pytest.mark.asyncio
    async def test_verify_credentials_new_success(self):
        mock_db = Mock()
        creds = UserCredentials(
            user_id="u1",
            username="a@b.com",
            email="a@b.com",
            roles=["member"],
            security_level="standard",
            permissions=[],
            mfa_enabled=False,
        )
        service = Mock()
        service.verify_credentials.return_value = creds

        def fake_get_db():
            yield mock_db

        with patch("core.database.get_db", fake_get_db), patch(
            "core.enterprise_auth_service.EnterpriseAuthService", return_value=service
        ):
            result = await _verify_enterprise_credentials_new("a@b.com", "pw")
        assert result["user_id"] == "u1"
        assert result["roles"] == ["member"]

    @pytest.mark.asyncio
    async def test_verify_credentials_new_invalid(self):
        mock_db = Mock()
        service = Mock()
        service.verify_credentials.return_value = None

        def fake_get_db():
            yield mock_db

        with patch("core.database.get_db", fake_get_db), patch(
            "core.enterprise_auth_service.EnterpriseAuthService", return_value=service
        ):
            result = await _verify_enterprise_credentials_new("a@b.com", "pw")
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_credentials_new_exception(self):
        mock_db = Mock()
        service = Mock()
        service.verify_credentials.side_effect = RuntimeError("boom")

        def fake_get_db():
            yield mock_db

        with patch("core.database.get_db", fake_get_db), patch(
            "core.enterprise_auth_service.EnterpriseAuthService", return_value=service
        ):
            result = await _verify_enterprise_credentials_new("a@b.com", "pw")
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_enterprise_credentials_legacy_delegates(self):
        expected = {"user_id": "u1"}
        with patch(
            "api.enterprise_auth_endpoints._verify_enterprise_credentials_new",
            new=AsyncMock(return_value=expected),
        ):
            result = await _verify_enterprise_credentials("a@b.com", "pw")
        assert result == expected


# ============================================================================
# Workflow debugging routes
# ============================================================================


class TestWorkflowDebuggingRoutes:
    def _create_session(self, auth_user_client, workflow_id="wf-1", session_name=None):
        payload = {"workflow_id": workflow_id}
        if session_name:
            payload["session_name"] = session_name
        return auth_user_client.post(
            f"/api/workflows/{workflow_id}/debug/sessions", json=payload
        )

    def test_create_debug_session_success(self, auth_user_client):
        resp = self._create_session(auth_user_client)
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"]
        assert body["status"] == "active"

    def test_create_debug_session_validation_422(self, auth_user_client):
        resp = auth_user_client.post("/api/workflows/wf-1/debug/sessions", json={})
        assert resp.status_code == 422

    def test_create_debug_session_internal_error_500(self, auth_user_client):
        with patch(
            "core.workflow_debugger.WorkflowDebugger.create_debug_session",
            side_effect=RuntimeError("boom"),
        ):
            resp = self._create_session(auth_user_client)
        assert resp.status_code == 500

    def test_create_debug_session_httpexception_passthrough(self, auth_user_client):
        with patch(
            "core.workflow_debugger.WorkflowDebugger.create_debug_session",
            side_effect=HTTPException(status_code=409, detail="conflict"),
        ):
            resp = self._create_session(auth_user_client)
        assert resp.status_code == 409

    def test_get_debug_sessions_httpexception_passthrough(self, auth_user_client):
        with patch(
            "core.workflow_debugger.WorkflowDebugger.get_active_debug_sessions",
            side_effect=HTTPException(status_code=409, detail="conflict"),
        ):
            resp = auth_user_client.get("/api/workflows/wf-1/debug/sessions")
        assert resp.status_code == 409

    def test_get_debug_sessions(self, auth_user_client):
        self._create_session(auth_user_client, session_name="s1")
        self._create_session(auth_user_client, session_name="s2")
        resp = auth_user_client.get("/api/workflows/wf-1/debug/sessions")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_debug_sessions_internal_error_500(self, auth_user_client):
        with patch(
            "core.workflow_debugger.WorkflowDebugger.get_active_debug_sessions",
            side_effect=RuntimeError("boom"),
        ):
            resp = auth_user_client.get("/api/workflows/wf-1/debug/sessions")
        assert resp.status_code == 500

    def test_pause_resume_complete_flow(self, auth_user_client):
        session_id = self._create_session(auth_user_client).json()["session_id"]

        resp = auth_user_client.post(f"/api/workflows/debug/sessions/{session_id}/pause")
        assert resp.status_code == 200

        resp = auth_user_client.post(f"/api/workflows/debug/sessions/{session_id}/resume")
        assert resp.status_code == 200

        resp = auth_user_client.post(f"/api/workflows/debug/sessions/{session_id}/complete")
        assert resp.status_code == 200

    def test_pause_resume_complete_not_found_404(self, auth_user_client):
        for action in ("pause", "resume", "complete"):
            resp = auth_user_client.post(
                f"/api/workflows/debug/sessions/does-not-exist/{action}"
            )
            assert resp.status_code == 404, action

    def test_pause_internal_error_500(self, auth_user_client):
        session_id = self._create_session(auth_user_client).json()["session_id"]
        with patch(
            "core.workflow_debugger.WorkflowDebugger.pause_debug_session",
            side_effect=RuntimeError("boom"),
        ):
            resp = auth_user_client.post(
                f"/api/workflows/debug/sessions/{session_id}/pause"
            )
        assert resp.status_code == 500

    def test_resume_internal_error_500(self, auth_user_client):
        session_id = self._create_session(auth_user_client).json()["session_id"]
        with patch(
            "core.workflow_debugger.WorkflowDebugger.resume_debug_session",
            side_effect=RuntimeError("boom"),
        ):
            resp = auth_user_client.post(
                f"/api/workflows/debug/sessions/{session_id}/resume"
            )
        assert resp.status_code == 500

    def test_complete_internal_error_500(self, auth_user_client):
        session_id = self._create_session(auth_user_client).json()["session_id"]
        with patch(
            "core.workflow_debugger.WorkflowDebugger.complete_debug_session",
            side_effect=RuntimeError("boom"),
        ):
            resp = auth_user_client.post(
                f"/api/workflows/debug/sessions/{session_id}/complete"
            )
        assert resp.status_code == 500

    def test_add_get_breakpoints(self, auth_user_client):
        resp = auth_user_client.post("/api/workflows/wf-1/debug/breakpoints", json={
            "workflow_id": "wf-1",
            "node_id": "node-a",
            "breakpoint_type": "node",
            "condition": "x > 5",
            "hit_limit": 3,
            "log_message": "hit",
        })
        assert resp.status_code == 200
        bp = resp.json()
        assert bp["node_id"] == "node-a"
        assert bp["is_active"] is True
        assert bp["hit_limit"] == 3

        resp = auth_user_client.get("/api/workflows/wf-1/debug/breakpoints")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        resp = auth_user_client.get("/api/workflows/wf-1/debug/breakpoints?active_only=false")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_add_breakpoint_validation_422(self, auth_user_client):
        resp = auth_user_client.post("/api/workflows/wf-1/debug/breakpoints", json={
            "node_id": "node-a",
        })
        assert resp.status_code == 422

    def test_add_breakpoint_internal_error_500(self, auth_user_client):
        with patch(
            "core.workflow_debugger.WorkflowDebugger.add_breakpoint",
            side_effect=RuntimeError("boom"),
        ):
            resp = auth_user_client.post("/api/workflows/wf-1/debug/breakpoints", json={
                "workflow_id": "wf-1",
                "node_id": "node-a",
            })
        assert resp.status_code == 500

    def test_get_breakpoints_internal_error_500(self, auth_user_client):
        with patch(
            "core.workflow_debugger.WorkflowDebugger.get_breakpoints",
            side_effect=RuntimeError("boom"),
        ):
            resp = auth_user_client.get("/api/workflows/wf-1/debug/breakpoints")
        assert resp.status_code == 500

    def test_remove_breakpoint(self, auth_user_client):
        bp_id = auth_user_client.post(
            "/api/workflows/wf-1/debug/breakpoints",
            json={"workflow_id": "wf-1", "node_id": "node-a"},
        ).json()["breakpoint_id"]

        resp = auth_user_client.delete(f"/api/workflows/debug/breakpoints/{bp_id}")
        assert resp.status_code == 200

        resp = auth_user_client.delete(f"/api/workflows/debug/breakpoints/{bp_id}")
        assert resp.status_code == 404

    def test_remove_breakpoint_internal_error_500(self, auth_user_client):
        with patch(
            "core.workflow_debugger.WorkflowDebugger.remove_breakpoint",
            side_effect=RuntimeError("boom"),
        ):
            resp = auth_user_client.delete("/api/workflows/debug/breakpoints/x")
        assert resp.status_code == 500

    def test_toggle_breakpoint(self, auth_user_client):
        bp_id = auth_user_client.post(
            "/api/workflows/wf-1/debug/breakpoints",
            json={"workflow_id": "wf-1", "node_id": "node-a"},
        ).json()["breakpoint_id"]

        resp = auth_user_client.put(f"/api/workflows/debug/breakpoints/{bp_id}/toggle")
        assert resp.status_code == 200
        assert resp.json()["is_disabled"] is True

        resp = auth_user_client.put(f"/api/workflows/debug/breakpoints/{bp_id}/toggle")
        assert resp.status_code == 200
        assert resp.json()["is_disabled"] is False

        resp = auth_user_client.put("/api/workflows/debug/breakpoints/zzz/toggle")
        assert resp.status_code == 404

    def test_toggle_breakpoint_internal_error_500(self, auth_user_client):
        with patch(
            "core.workflow_debugger.WorkflowDebugger.toggle_breakpoint",
            side_effect=RuntimeError("boom"),
        ):
            resp = auth_user_client.put("/api/workflows/debug/breakpoints/x/toggle")
        assert resp.status_code == 500

    def test_step_execution_actions(self, auth_user_client):
        session_id = self._create_session(auth_user_client).json()["session_id"]
        for action in ("step_over", "step_into", "continue", "pause"):
            resp = auth_user_client.post("/api/workflows/debug/step", json={
                "session_id": session_id,
                "action": action,
            })
            assert resp.status_code == 200, action
            assert resp.json()["action"] == action

    def test_step_out_empty_call_stack_404(self, auth_user_client):
        session_id = self._create_session(auth_user_client).json()["session_id"]
        resp = auth_user_client.post("/api/workflows/debug/step", json={
            "session_id": session_id,
            "action": "step_out",
        })
        assert resp.status_code == 404

    def test_step_session_not_found_404(self, auth_user_client):
        resp = auth_user_client.post("/api/workflows/debug/step", json={
            "session_id": "nope",
            "action": "step_over",
        })
        assert resp.status_code == 404

    def test_step_invalid_action_422(self, auth_user_client):
        resp = auth_user_client.post("/api/workflows/debug/step", json={
            "session_id": "x",
            "action": "teleport",
        })
        assert resp.status_code == 422

    def test_step_internal_error_500(self, auth_user_client):
        session_id = self._create_session(auth_user_client).json()["session_id"]
        with patch(
            "core.workflow_debugger.WorkflowDebugger.step_over",
            side_effect=RuntimeError("boom"),
        ):
            resp = auth_user_client.post("/api/workflows/debug/step", json={
                "session_id": session_id,
                "action": "step_over",
            })
        assert resp.status_code == 500

    def test_create_and_complete_trace(self, auth_user_client):
        session_id = self._create_session(auth_user_client).json()["session_id"]
        resp = auth_user_client.post("/api/workflows/debug/traces", json={
            "workflow_id": "wf-1",
            "execution_id": "exec-1",
            "step_number": 1,
            "node_id": "node-a",
            "node_type": "action",
            "input_data": {"k": "v"},
            "variables_before": {"x": 1},
            "debug_session_id": session_id,
        })
        assert resp.status_code == 200
        trace_id = resp.json()["trace_id"]
        assert resp.json()["status"] == "started"

        resp = auth_user_client.put(f"/api/workflows/debug/traces/{trace_id}/complete", json={
            "output_data": {"result": 2},
            "variables_after": {"x": 2},
        })
        assert resp.status_code == 200

        resp = auth_user_client.put(
            f"/api/workflows/debug/traces/{trace_id}/complete",
            json={"error_message": "step failed"},
        )
        assert resp.status_code == 200

    def test_complete_trace_not_found_404(self, auth_user_client):
        resp = auth_user_client.put(
            "/api/workflows/debug/traces/nope/complete", json={}
        )
        assert resp.status_code == 404

    def test_create_trace_internal_error_500(self, auth_user_client):
        with patch(
            "core.workflow_debugger.WorkflowDebugger.create_trace",
            side_effect=RuntimeError("boom"),
        ):
            resp = auth_user_client.post("/api/workflows/debug/traces", json={
                "workflow_id": "wf-1",
                "execution_id": "exec-1",
                "step_number": 1,
                "node_id": "node-a",
                "node_type": "action",
            })
        assert resp.status_code == 500

    def test_complete_trace_internal_error_500(self, auth_user_client):
        with patch(
            "core.workflow_debugger.WorkflowDebugger.complete_trace",
            side_effect=RuntimeError("boom"),
        ):
            resp = auth_user_client.put(
                "/api/workflows/debug/traces/x/complete", json={}
            )
        assert resp.status_code == 500

    def test_get_execution_traces(self, auth_user_client):
        session_id = self._create_session(auth_user_client).json()["session_id"]
        for step in (1, 2):
            auth_user_client.post("/api/workflows/debug/traces", json={
                "workflow_id": "wf-1",
                "execution_id": "exec-1",
                "step_number": step,
                "node_id": f"node-{step}",
                "node_type": "action",
                "debug_session_id": session_id,
            })
        resp = auth_user_client.get("/api/workflows/executions/exec-1/traces")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

        resp = auth_user_client.get(
            f"/api/workflows/executions/exec-1/traces?debug_session_id={session_id}&limit=1"
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        resp = auth_user_client.get("/api/workflows/executions/exec-1/traces?limit=0")
        assert resp.status_code == 422

    def test_get_execution_traces_internal_error_500(self, auth_user_client):
        with patch(
            "core.workflow_debugger.WorkflowDebugger.get_execution_traces",
            side_effect=RuntimeError("boom"),
        ):
            resp = auth_user_client.get("/api/workflows/executions/exec-1/traces")
        assert resp.status_code == 500

    def test_get_session_variables(self, auth_user_client, db):
        session_id = self._create_session(auth_user_client).json()["session_id"]
        trace = ExecutionTrace(
            workflow_id="wf-1",
            execution_id="exec-1",
            step_number=1,
            node_id="node-a",
            node_type="action",
            status="completed",
            debug_session_id=session_id,
        )
        db.add(trace)
        db.commit()
        db.refresh(trace)
        var = DebugVariable(
            trace_id=trace.id,
            debug_session_id=session_id,
            variable_name="x",
            variable_path="x",
            variable_type="int",
            value=1,
            value_preview="1",
            is_mutable=True,
            scope="local",
            is_changed=False,
            previous_value=None,
            is_watch=True,
            watch_expression="x",
        )
        db.add(var)
        db.commit()

        resp = auth_user_client.get(f"/api/workflows/debug/sessions/{session_id}/variables")
        assert resp.status_code == 200
        assert resp.json()[0]["variable_name"] == "x"
        assert resp.json()[0]["is_watch"] is True

        resp = auth_user_client.get(f"/api/workflows/debug/traces/{trace.id}/variables")
        assert resp.status_code == 200
        assert resp.json()[0]["variable_name"] == "x"

    def test_variables_internal_error_500(self, auth_user_client):
        with patch(
            "core.workflow_debugger.WorkflowDebugger.get_watch_variables",
            side_effect=RuntimeError("boom"),
        ):
            resp = auth_user_client.get(
                "/api/workflows/debug/sessions/x/variables"
            )
        assert resp.status_code == 500

        with patch(
            "core.workflow_debugger.WorkflowDebugger.get_variables_for_trace",
            side_effect=RuntimeError("boom"),
        ):
            resp = auth_user_client.get("/api/workflows/debug/traces/x/variables")
        assert resp.status_code == 500

    def test_add_breakpoint_httpexception_passthrough(self, auth_user_client):
        with patch(
            "core.workflow_debugger.WorkflowDebugger.add_breakpoint",
            side_effect=HTTPException(status_code=409, detail="conflict"),
        ):
            resp = auth_user_client.post("/api/workflows/wf-1/debug/breakpoints", json={
                "workflow_id": "wf-1",
                "node_id": "node-a",
            })
        assert resp.status_code == 409

    def test_get_breakpoints_httpexception_passthrough(self, auth_user_client):
        with patch(
            "core.workflow_debugger.WorkflowDebugger.get_breakpoints",
            side_effect=HTTPException(status_code=409, detail="conflict"),
        ):
            resp = auth_user_client.get("/api/workflows/wf-1/debug/breakpoints")
        assert resp.status_code == 409

    def test_create_trace_httpexception_passthrough(self, auth_user_client):
        with patch(
            "core.workflow_debugger.WorkflowDebugger.create_trace",
            side_effect=HTTPException(status_code=409, detail="conflict"),
        ):
            resp = auth_user_client.post("/api/workflows/debug/traces", json={
                "workflow_id": "wf-1",
                "execution_id": "exec-1",
                "step_number": 1,
                "node_id": "node-a",
                "node_type": "action",
            })
        assert resp.status_code == 409

    def test_get_execution_traces_httpexception_passthrough(self, auth_user_client):
        with patch(
            "core.workflow_debugger.WorkflowDebugger.get_execution_traces",
            side_effect=HTTPException(status_code=409, detail="conflict"),
        ):
            resp = auth_user_client.get("/api/workflows/executions/exec-1/traces")
        assert resp.status_code == 409

    def test_session_variables_httpexception_passthrough(self, auth_user_client):
        with patch(
            "core.workflow_debugger.WorkflowDebugger.get_watch_variables",
            side_effect=HTTPException(status_code=409, detail="conflict"),
        ):
            resp = auth_user_client.get("/api/workflows/debug/sessions/x/variables")
        assert resp.status_code == 409

    def test_trace_variables_httpexception_passthrough(self, auth_user_client):
        with patch(
            "core.workflow_debugger.WorkflowDebugger.get_variables_for_trace",
            side_effect=HTTPException(status_code=409, detail="conflict"),
        ):
            resp = auth_user_client.get("/api/workflows/debug/traces/x/variables")
        assert resp.status_code == 409

    def test_workflow_routes_require_auth(self, client):
        resp = client.get("/api/workflows/wf-1/debug/sessions")
        assert resp.status_code == 401


# ============================================================================
# Social media routes
# ============================================================================


def _insert_tenant(db):
    tenant = Tenant(
        id=str(uuid.uuid4()),
        name="Test Tenant",
        subdomain=f"t-{uuid.uuid4().hex[:8]}",
        plan_type="free",
        edition="personal",
    )
    db.add(tenant)
    db.commit()
    return tenant


def _insert_token(db, user, provider="twitter", token="tok-123"):
    token_row = IntegrationToken(
        id=str(uuid.uuid4()),
        tenant_id=_insert_tenant(db).id,
        user_id=user.id,
        provider=provider,
        access_token=token,
        scope="tweet.write",
        status="active",
    )
    db.add(token_row)
    db.commit()
    db.refresh(token_row)
    return token_row


def _insert_posted_history(db, user, count=10):
    for _ in range(count):
        row = SocialPostHistory(
            post_id=str(uuid.uuid4()),
            user_id=user.id,
            content="posted",
            platforms=["twitter"],
            status="posted",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        )
        db.add(row)
    db.commit()


class TestSocialPlatforms:
    def test_list_platforms(self, client):
        resp = client.get("/api/v1/social/platforms")
        assert resp.status_code == 200
        assert resp.json()["total"] == 3
        assert "twitter" in resp.json()["platforms"]

    def test_platform_config_validation(self):
        assert PlatformConfig.validate_content("twitter", "hi") == (True, None)
        ok, err = PlatformConfig.validate_content("twitter", "x" * 501)
        assert ok is False and "max length" in err
        ok, err = PlatformConfig.validate_content("instagram", "hi")
        assert ok is False and "Unsupported platform" in err
        with pytest.raises(ValueError):
            PlatformConfig.get_platform("nope")


class TestCreateSocialPost:
    @pytest.fixture
    def mock_posters(self):
        posters = {
            "twitter": AsyncMock(return_value={"success": True, "post_id": "t-1", "platform": "twitter"}),
            "linkedin": AsyncMock(return_value={"success": True, "post_id": "l-1", "platform": "linkedin"}),
            "facebook": AsyncMock(return_value={"success": True, "post_id": "f-1", "platform": "facebook"}),
        }
        with patch("api.social_media_routes.PLATFORM_POSTERS", posters):
            yield posters

    def test_post_success_with_tokens(self, auth_user_client, auth_user, db, mock_posters):
        _insert_token(db, auth_user, "twitter")
        _insert_token(db, auth_user, "linkedin")
        resp = auth_user_client.post("/api/v1/social/post", json={
            "text": "Hello world",
            "platforms": ["twitter", "linkedin"],
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "twitter" in body["platform_results"]
        assert "linkedin" in body["platform_results"]
        mock_posters["twitter"].assert_awaited_once()
        mock_posters["linkedin"].assert_awaited_once()
        audits = db.query(SocialMediaAudit).all()
        assert len(audits) == 2
        assert all(a.success for a in audits)

    def test_post_with_link_url_and_media(self, auth_user_client, auth_user, db, mock_posters):
        _insert_token(db, auth_user, "twitter")
        resp = auth_user_client.post("/api/v1/social/post", json={
            "text": "Hello world",
            "platforms": ["twitter"],
            "media_urls": ["https://example.com/img.png"],
            "link_url": "https://example.com",
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_post_no_token_audits_failure(self, auth_user_client, auth_user, db):
        resp = auth_user_client.post("/api/v1/social/post", json={
            "text": "Hello world",
            "platforms": ["twitter"],
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert "No active" in body["platform_results"]["twitter"]["error"]
        audit = db.query(SocialMediaAudit).first()
        assert audit is not None
        assert audit.success is False
        assert audit.governance_check_passed is True

    def test_post_mixed_partial_success(self, auth_user_client, auth_user, db, mock_posters):
        _insert_token(db, auth_user, "twitter")
        resp = auth_user_client.post("/api/v1/social/post", json={
            "text": "Hello world",
            "platforms": ["twitter", "facebook"],
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["platform_results"]["facebook"]["success"] is False
        mock_posters["twitter"].assert_awaited_once()
        mock_posters["facebook"].assert_not_awaited()

    def test_post_poster_raises_exception(self, auth_user_client, auth_user, db):
        _insert_token(db, auth_user, "twitter")
        async def boom(*args, **kwargs):
            raise RuntimeError("network down")

        with patch("api.social_media_routes.PLATFORM_POSTERS", {"twitter": boom}):
            resp = auth_user_client.post("/api/v1/social/post", json={
                "text": "Hello world",
                "platforms": ["twitter"],
            })
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert body["platform_results"]["twitter"]["error"] == "Posting failed"

    def test_post_poster_raises_value_error(self, auth_user_client, auth_user, db):
        _insert_token(db, auth_user, "twitter")
        async def valerr(*args, **kwargs):
            raise ValueError("bad platform")

        with patch("api.social_media_routes.PLATFORM_POSTERS", {"twitter": valerr}):
            resp = auth_user_client.post("/api/v1/social/post", json={
                "text": "Hello world",
                "platforms": ["twitter"],
            })
        assert resp.status_code == 200
        assert resp.json()["platform_results"]["twitter"]["error"] == "Posting failed"

    def test_post_empty_platforms_422(self, auth_user_client):
        resp = auth_user_client.post("/api/v1/social/post", json={
            "text": "Hello",
            "platforms": [],
        })
        assert resp.status_code == 422

    def test_post_missing_platforms_422(self, auth_user_client):
        resp = auth_user_client.post("/api/v1/social/post", json={"text": "Hello"})
        assert resp.status_code == 422

    def test_post_unsupported_platform_422(self, auth_user_client):
        resp = auth_user_client.post("/api/v1/social/post", json={
            "text": "Hello",
            "platforms": ["instagram"],
        })
        assert resp.status_code == 422

    def test_post_platform_not_implemented(self, auth_user_client, auth_user, db):
        _insert_token(db, auth_user, "twitter")
        with patch("api.social_media_routes.PLATFORM_POSTERS", {}):
            resp = auth_user_client.post("/api/v1/social/post", json={
                "text": "Hello",
                "platforms": ["twitter"],
            })
        assert resp.status_code == 200
        assert resp.json()["success"] is False
        assert "not yet implemented" in resp.json()["platform_results"]["twitter"]["error"]

    def test_post_twitter_length_422(self, auth_user_client):
        resp = auth_user_client.post("/api/v1/social/post", json={
            "text": "x" * 501,
            "platforms": ["twitter"],
        })
        assert resp.status_code == 422

    def test_post_facebook_allows_long_text(self, auth_user_client, auth_user, db, mock_posters):
        _insert_token(db, auth_user, "facebook")
        resp = auth_user_client.post("/api/v1/social/post", json={
            "text": "y" * 1000,
            "platforms": ["facebook"],
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_post_empty_text_422(self, auth_user_client):
        resp = auth_user_client.post("/api/v1/social/post", json={
            "text": "",
            "platforms": ["twitter"],
        })
        assert resp.status_code == 422

    def test_post_rate_limited_429(self, auth_user_client, auth_user, db):
        _insert_posted_history(db, auth_user, count=10)
        resp = auth_user_client.post("/api/v1/social/post", json={
            "text": "Hello",
            "platforms": ["twitter"],
        })
        assert resp.status_code == 429

    def test_post_rate_limit_not_exceeded_with_9(self, auth_user_client, auth_user, db, mock_posters):
        _insert_posted_history(db, auth_user, count=9)
        _insert_token(db, auth_user, "twitter")
        resp = auth_user_client.post("/api/v1/social/post", json={
            "text": "Hello",
            "platforms": ["twitter"],
        })
        assert resp.status_code == 200

    def test_post_scheduled_future(self, auth_user_client, auth_user, db):
        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        with patch(
            "core.task_queue.enqueue_scheduled_post", return_value="job-123"
        ) as mock_enqueue:
            resp = auth_user_client.post("/api/v1/social/post", json={
                "text": "Scheduled hello",
                "platforms": ["twitter"],
                "scheduled_for": future,
            })
        assert resp.status_code == 200
        body = resp.json()
        assert body["scheduled"] is True
        assert body["platform_results"]["job_id"] == "job-123"
        mock_enqueue.assert_called_once()
        history = db.query(SocialPostHistory).first()
        assert history is not None
        assert history.status == "scheduled"
        assert history.post_id == body["post_id"]

    def test_post_scheduled_queue_unavailable_500(self, auth_user_client):
        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        with patch("core.task_queue.enqueue_scheduled_post", return_value=None):
            resp = auth_user_client.post("/api/v1/social/post", json={
                "text": "Scheduled hello",
                "platforms": ["twitter"],
                "scheduled_for": future,
            })
        assert resp.status_code == 500

    def test_post_scheduled_in_past_posts_immediately(
        self, auth_user_client, auth_user, db, mock_posters
    ):
        past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        _insert_token(db, auth_user, "twitter")
        resp = auth_user_client.post("/api/v1/social/post", json={
            "text": "Immediate",
            "platforms": ["twitter"],
            "scheduled_for": past,
        })
        assert resp.status_code == 200
        assert resp.json()["scheduled"] is False

    def test_post_governance_denied_403(self, auth_user_client, auth_user, db):
        agent = SimpleNamespace(id="agent-1", status="STUDENT")
        with patch(
            "core.agent_context_resolver.AgentContextResolver.resolve_agent_for_request",
            new=AsyncMock(return_value=(agent, {})),
        ), patch(
            "core.agent_governance_service.AgentGovernanceService.can_perform_action",
            return_value={"allowed": False, "requires_human_approval": True},
        ):
            resp = auth_user_client.post("/api/v1/social/post", json={
                "text": "Agent hello",
                "platforms": ["twitter"],
                "agent_id": "agent-1",
            })
        assert resp.status_code == 403
        audit = db.query(SocialMediaAudit).first()
        assert audit is not None
        assert audit.agent_id == "agent-1"
        assert audit.governance_check_passed is False
        assert audit.error_message == "Governance check failed"

    def test_post_governance_allowed_with_agent(self, auth_user_client, auth_user, db, mock_posters):
        agent = SimpleNamespace(id="agent-2", status="AUTONOMOUS")
        _insert_token(db, auth_user, "twitter")
        with patch(
            "core.agent_context_resolver.AgentContextResolver.resolve_agent_for_request",
            new=AsyncMock(return_value=(agent, {})),
        ), patch(
            "core.agent_governance_service.AgentGovernanceService.can_perform_action",
            return_value={"allowed": True, "requires_human_approval": False},
        ):
            resp = auth_user_client.post("/api/v1/social/post", json={
                "text": "Agent hello",
                "platforms": ["twitter"],
                "agent_id": "agent-2",
            })
        assert resp.status_code == 200
        audit = db.query(SocialMediaAudit).first()
        assert audit.agent_id == "agent-2"
        assert audit.agent_maturity == "AUTONOMOUS"

    def test_post_unexpected_error_500(self, auth_user_client, db):
        with patch(
            "api.social_media_routes.rate_limit_check",
            side_effect=RuntimeError("db down"),
        ):
            resp = auth_user_client.post("/api/v1/social/post", json={
                "text": "Hello",
                "platforms": ["twitter"],
            })
        assert resp.status_code == 500

    def test_social_post_request_model(self):
        req = SocialPostRequest(text="hi", platforms=["twitter"], extra_field="kept")
        assert req.text == "hi"
        assert req.media_urls == []
        assert req.extra_field == "kept"


class TestConnectedAccounts:
    def test_list_connected_accounts(self, auth_user_client, auth_user, db):
        _insert_token(db, auth_user, "twitter")
        _insert_token(db, auth_user, "linkedin")
        _insert_token(db, auth_user, "slack")
        resp = auth_user_client.get("/api/v1/social/connected-accounts")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        providers = {a["provider"] for a in body["accounts"]}
        assert providers == {"twitter", "linkedin"}

    def test_list_connected_accounts_empty(self, auth_user_client):
        resp = auth_user_client.get("/api/v1/social/connected-accounts")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_list_connected_accounts_internal_error_500(self, auth_user_client, db):
        class _BoomPlatforms:
            def items(self):
                raise RuntimeError("boom")

            def get(self, *args, **kwargs):
                raise RuntimeError("boom")

        with patch(
            "api.social_media_routes.PlatformConfig.PLATFORMS", _BoomPlatforms()
        ):
            resp = auth_user_client.get("/api/v1/social/connected-accounts")
        assert resp.status_code == 500


class TestRateLimitStatus:
    def test_rate_limit_status(self, auth_user_client, auth_user, db):
        _insert_posted_history(db, auth_user, count=4)
        resp = auth_user_client.get("/api/v1/social/rate-limit")
        assert resp.status_code == 200
        body = resp.json()
        assert body["limit"] == 10
        assert body["used"] == 4
        assert body["remaining"] == 6

    def test_rate_limit_status_zero(self, auth_user_client):
        resp = auth_user_client.get("/api/v1/social/rate-limit")
        assert resp.status_code == 200
        assert resp.json()["used"] == 0

    def test_rate_limit_status_internal_error_500(self, auth_user_client, db):
        with patch(
            "api.social_media_routes.SocialPostHistory",
            side_effect=RuntimeError("boom"),
        ):
            resp = auth_user_client.get("/api/v1/social/rate-limit")
        assert resp.status_code == 500

    def test_social_routes_require_auth(self, client):
        assert client.get("/api/v1/social/rate-limit").status_code == 401
        assert client.get("/api/v1/social/connected-accounts").status_code == 401
        assert client.post(
            "/api/v1/social/post", json={"text": "hi", "platforms": ["twitter"]}
        ).status_code == 401


# ============================================================================
# Platform poster functions (direct, with mocked httpx)
# ============================================================================


class _FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class _FakeHttpClient:
    def __init__(self, get=None, post=None):
        self._get = get
        self._post = post

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, headers=None):
        return await self._get(url, headers=headers)

    async def post(self, url, json=None, data=None, headers=None, timeout=None):
        kwargs = {}
        if json is not None:
            kwargs["json"] = json
        if data is not None:
            kwargs["data"] = data
        return await self._post(url, headers=headers, timeout=timeout, **kwargs)


class TestPostToTwitter:
    @pytest.mark.asyncio
    async def test_success(self):
        async def post(url, json=None, headers=None, timeout=None):
            return _FakeResponse(201, {"data": {"id": "tweet-1"}})

        with patch("httpx.AsyncClient", return_value=_FakeHttpClient(post=post)):
            result = await post_to_twitter("hello", "tok", link_url="https://x.com")
        assert result["success"] is True
        assert result["post_id"] == "tweet-1"

    @pytest.mark.asyncio
    async def test_unauthorized(self):
        async def post(url, json=None, headers=None, timeout=None):
            return _FakeResponse(401)

        with patch("httpx.AsyncClient", return_value=_FakeHttpClient(post=post)):
            result = await post_to_twitter("hello", "tok")
        assert result["success"] is False
        assert "reconnect" in result["error"]

    @pytest.mark.asyncio
    async def test_rate_limited(self):
        async def post(url, json=None, headers=None, timeout=None):
            return _FakeResponse(429)

        with patch("httpx.AsyncClient", return_value=_FakeHttpClient(post=post)):
            result = await post_to_twitter("hello", "tok")
        assert result["success"] is False
        assert "Rate limit" in result["error"]

    @pytest.mark.asyncio
    async def test_api_error(self):
        async def post(url, json=None, headers=None, timeout=None):
            return _FakeResponse(500, text="server exploded")

        with patch("httpx.AsyncClient", return_value=_FakeHttpClient(post=post)):
            result = await post_to_twitter("hello", "tok")
        assert result["success"] is False
        assert result["status_code"] == 500

    @pytest.mark.asyncio
    async def test_import_error(self):
        with patch.dict(sys.modules, {"httpx": None}):
            result = await post_to_twitter("hello", "tok")
        assert result["success"] is False
        assert "httpx" in result["error"]

    @pytest.mark.asyncio
    async def test_generic_exception(self):
        with patch("httpx.AsyncClient", side_effect=RuntimeError("boom")):
            result = await post_to_twitter("hello", "tok")
        assert result["success"] is False
        assert result["error"] == "Posting failed"


class TestPostToLinkedIn:
    @pytest.mark.asyncio
    async def test_success(self):
        async def get(url, headers=None):
            return _FakeResponse(200, {"sub": "person-1"})

        async def post(url, json=None, headers=None, timeout=None):
            return _FakeResponse(201, {"id": "post-1"})

        with patch("httpx.AsyncClient", return_value=_FakeHttpClient(get=get, post=post)):
            result = await post_to_linkedin("hello", "tok", link_url="https://x.com")
        assert result["success"] is True
        assert result["post_id"] == "post-1"

    @pytest.mark.asyncio
    async def test_profile_failure(self):
        async def get(url, headers=None):
            return _FakeResponse(403)

        with patch("httpx.AsyncClient", return_value=_FakeHttpClient(get=get)):
            result = await post_to_linkedin("hello", "tok")
        assert result["success"] is False
        assert result["status_code"] == 403

    @pytest.mark.asyncio
    async def test_missing_profile_id(self):
        async def get(url, headers=None):
            return _FakeResponse(200, {})

        with patch("httpx.AsyncClient", return_value=_FakeHttpClient(get=get)):
            result = await post_to_linkedin("hello", "tok")
        assert result["success"] is False
        assert "profile ID" in result["error"]

    @pytest.mark.asyncio
    async def test_post_error(self):
        async def get(url, headers=None):
            return _FakeResponse(200, {"sub": "person-1"})

        async def post(url, json=None, headers=None, timeout=None):
            return _FakeResponse(400, text="bad request")

        with patch("httpx.AsyncClient", return_value=_FakeHttpClient(get=get, post=post)):
            result = await post_to_linkedin("hello", "tok")
        assert result["success"] is False
        assert result["status_code"] == 400

    @pytest.mark.asyncio
    async def test_import_error(self):
        with patch.dict(sys.modules, {"httpx": None}):
            result = await post_to_linkedin("hello", "tok")
        assert result["success"] is False
        assert "httpx" in result["error"]

    @pytest.mark.asyncio
    async def test_generic_exception(self):
        with patch("httpx.AsyncClient", side_effect=RuntimeError("boom")):
            result = await post_to_linkedin("hello", "tok")
        assert result["success"] is False
        assert result["error"] == "Posting failed"


class TestPostToFacebook:
    @pytest.mark.asyncio
    async def test_success(self):
        async def post(url, data=None, headers=None, timeout=None):
            return _FakeResponse(200, {"id": "fb-post-1"})

        with patch("httpx.AsyncClient", return_value=_FakeHttpClient(post=post)):
            result = await post_to_facebook("hello", "tok", link_url="https://x.com")
        assert result["success"] is True
        assert result["post_id"] == "fb-post-1"

    @pytest.mark.asyncio
    async def test_api_error(self):
        async def post(url, data=None, headers=None, timeout=None):
            return _FakeResponse(500, text="boom")

        with patch("httpx.AsyncClient", return_value=_FakeHttpClient(post=post)):
            result = await post_to_facebook("hello", "tok")
        assert result["success"] is False
        assert result["status_code"] == 500

    @pytest.mark.asyncio
    async def test_import_error(self):
        with patch.dict(sys.modules, {"httpx": None}):
            result = await post_to_facebook("hello", "tok")
        assert result["success"] is False
        assert "httpx" in result["error"]

    @pytest.mark.asyncio
    async def test_generic_exception(self):
        with patch("httpx.AsyncClient", side_effect=RuntimeError("boom")):
            result = await post_to_facebook("hello", "tok")
        assert result["success"] is False
        assert result["error"] == "Posting failed"
