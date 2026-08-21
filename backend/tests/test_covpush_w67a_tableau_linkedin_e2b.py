"""Coverage wave W67a — Tableau + LinkedIn integration routes + E2B sandbox runner.

Targets (>=95% statement coverage, standalone):
- integrations/tableau_routes.py   (was UNIMPORTABLE — phantom get_tableau_service
  factory; router unmountable -> every /api/tableau/* route 404'd)
- integrations/linkedin_routes.py  (was UNIMPORTABLE in real-branch sense —
  phantom get_linkedin_service factory left LINKEDIN_AVAILABLE stuck False)
- core/sandbox_runtime/e2b_runner.py (was 42%, is_available probe only)

Pattern: FastAPI TestClient + patch on the REAL module the app imports
(`integrations.<module>`, NOT `backend.integrations.<module>` — the backend/
prefix is a phantom double-import and patches miss). Patch context wraps the
REQUEST, not client construction. No network, no LLM, no DB.

Bugs found + fixed in the assigned modules (regression tests below):
1. tableau_routes.py — `from .tableau_service import get_tableau_service`
   unguarded, but no such factory exists (singleton commented out, "use
   IntegrationRegistry instead") -> ImportError at import -> router unmountable
   (every /api/tableau/* route 404'd). Now try/except-guarded with a local
   factory constructing TableauService directly (W65c twilio precedent) —
   test_tableau_router_mounts / test_tableau_get_service_factory.
2. linkedin_routes.py — same phantom factory, but the import was guarded so the
   failure was SILENT: LINKEDIN_AVAILABLE stuck False, /profile and /share
   permanently 501 and real OAuth branches dead. Factory now constructs
   LinkedInService directly — test_linkedin_router_mounts /
   test_linkedin_get_service_factory.
3. linkedin_routes.py:94,142 — `logger.error(...)` in both exception handlers
   but `logger` was never defined (no `import logging`, no getLogger) ->
   NameError inside the except block -> 500 instead of the intended 400.
   Added module-level logger — test_profile_service_exception_maps_to_400 /
   test_share_service_exception_maps_to_400.
4. tableau_routes.py:125 + linkedin_routes.py:165 — `await service.health_check()`
   but both services' health_check are SYNC methods -> TypeError -> Tableau
   /health ALWAYS returned unhealthy, LinkedIn /health 500'd. Removed the
   await — test_health_sync_returns_healthy / test_health_available_returns_health.
"""
import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import sandbox_runtime
from core.sandbox_policy import SandboxPolicy
from core.sandbox_runtime.base import SandboxExecResult
from core.sandbox_runtime import e2b_runner


def make_client(router, authed=False):
    from core.auth import get_current_user
    from unittest.mock import MagicMock

    app = FastAPI()
    app.include_router(router)
    if authed:
        # R80c: linkedin/tableau data routes now require authentication.
        user = MagicMock()
        user.id = "w67a-user"
        user.email = "w67a@x.com"
        app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


def _policy(**kw):
    defaults = dict(
        run_id="run-1",
        agent_id="agent-1",
        tier_at_issuance="SUPERVISED",
        max_bytes_written=1000,
        max_exec_seconds=30,
        max_tool_calls=5,
    )
    defaults.update(kw)
    return SandboxPolicy(**defaults)


def _svc(methods, **attrs):
    """Build a MagicMock service with AsyncMock method stubs."""
    svc = MagicMock()
    for name, ret in methods.items():
        if isinstance(ret, Exception):
            setattr(svc, name, AsyncMock(side_effect=ret))
        else:
            setattr(svc, name, AsyncMock(return_value=ret))
    for name, val in attrs.items():
        setattr(svc, name, val)
    return svc


# ---------------------------------------------------------------------------
# integrations/tableau_routes.py
# ---------------------------------------------------------------------------

class TestTableauRoutes:
    def _call(self, method, path, svc, **kw):
        """Perform a request with get_tableau_service patched for its duration."""
        from integrations.tableau_routes import router

        with patch("integrations.tableau_routes.get_tableau_service", return_value=svc):
            resp = getattr(make_client(router, authed=True), method)(path, **kw)
        return resp

    def _plain(self, method, path, **kw):
        from integrations.tableau_routes import router

        return getattr(make_client(router, authed=True), method)(path, **kw)

    def test_tableau_router_mounts(self):
        """REGRESSION: phantom get_tableau_service factory -> ImportError -> 404."""
        resp = self._plain("get", "/api/tableau/auth/url")
        assert resp.status_code == 200
        assert "url" in resp.json()

    def test_tableau_get_service_factory(self):
        from integrations.tableau_routes import TABLEAU_AVAILABLE, get_tableau_service
        from integrations.tableau_service import TableauService

        assert TABLEAU_AVAILABLE is True
        assert isinstance(get_tableau_service(), TableauService)

    def test_get_auth_url_success(self):
        resp = self._plain("get", "/api/tableau/auth/url")
        assert resp.status_code == 200
        body = resp.json()
        assert body["url"] == "https://10ax.online.tableau.com"
        assert "timestamp" in body

    def test_sign_in_success(self):
        svc = _svc({"sign_in": {"token": "tok-123", "site": "main"}})
        resp = self._call(
            "post",
            "/api/tableau/auth/signin",
            svc,
            json={"username": "alice", "password": "pw", "site_content_url": "main"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"] == {"token": "tok-123", "site": "main"}
        svc.sign_in.assert_awaited_once_with("alice", "pw", "main")

    def test_sign_in_default_site(self):
        svc = _svc({"sign_in": {"token": "tok"}})
        resp = self._call(
            "post",
            "/api/tableau/auth/signin",
            svc,
            json={"username": "bob", "password": "pw"},
        )
        assert resp.status_code == 200
        svc.sign_in.assert_awaited_once_with("bob", "pw", "")

    def test_sign_in_service_exception_401(self):
        svc = _svc({"sign_in": RuntimeError("bad creds")})
        resp = self._call(
            "post",
            "/api/tableau/auth/signin",
            svc,
            json={"username": "a", "password": "b"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Internal error"

    def test_sign_in_missing_fields_422(self):
        resp = self._plain("post", "/api/tableau/auth/signin", json={"username": "a"})
        assert resp.status_code == 422

    def test_get_workbooks_success(self):
        svc = _svc({"get_workbooks": [{"id": 1, "name": "wb"}]})
        resp = self._call("get", "/api/tableau/workbooks", svc, params={"auth_token": "tok"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["workbooks"] == [{"id": 1, "name": "wb"}]
        assert body["count"] == 1
        svc.get_workbooks.assert_awaited_once_with("tok")

    def test_get_workbooks_no_token(self):
        svc = _svc({"get_workbooks": []})
        resp = self._call("get", "/api/tableau/workbooks", svc)
        assert resp.status_code == 200
        assert resp.json()["count"] == 0
        svc.get_workbooks.assert_awaited_once_with(None)

    def test_get_workbooks_exception_500(self):
        svc = _svc({"get_workbooks": ValueError("boom")})
        resp = self._call("get", "/api/tableau/workbooks", svc)
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"

    def test_get_views_success(self):
        svc = _svc({"get_views": [{"id": 7}]})
        resp = self._call("get", "/api/tableau/views", svc, params={"auth_token": "tok"})
        assert resp.status_code == 200
        assert resp.json()["views"] == [{"id": 7}]
        assert resp.json()["count"] == 1
        svc.get_views.assert_awaited_once_with("tok")

    def test_get_views_exception_500(self):
        svc = _svc({"get_views": RuntimeError("boom")})
        resp = self._call("get", "/api/tableau/views", svc)
        assert resp.status_code == 500

    def test_get_datasources_success(self):
        svc = _svc({"get_datasources": [{"id": 9, "name": "ds"}]})
        resp = self._call(
            "get", "/api/tableau/datasources", svc, params={"auth_token": "tok"}
        )
        assert resp.status_code == 200
        assert resp.json()["datasources"] == [{"id": 9, "name": "ds"}]
        assert resp.json()["count"] == 1
        svc.get_datasources.assert_awaited_once_with("tok")

    def test_get_datasources_exception_500(self):
        svc = _svc({"get_datasources": OSError("boom")})
        resp = self._call("get", "/api/tableau/datasources", svc)
        assert resp.status_code == 500

    def test_status_success(self):
        resp = self._plain("get", "/api/tableau/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["status"] == "active"
        assert body["capabilities"] == ["workbooks", "views", "datasources"]

    def test_health_sync_returns_healthy(self):
        """REGRESSION: health_check is SYNC; `await` raised TypeError so /health
        ALWAYS returned unhealthy."""
        svc = _svc({})
        svc.health_check = MagicMock(
            return_value={"ok": True, "status": "healthy", "service": "tableau"}
        )
        resp = self._call("get", "/api/tableau/health", svc)
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["status"] == "healthy"
        svc.health_check.assert_called_once()

    def test_health_exception_returns_unhealthy(self):
        svc = _svc({})
        svc.health_check = MagicMock(side_effect=RuntimeError("down"))
        resp = self._call("get", "/api/tableau/health", svc)
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert body["status"] == "unhealthy"
        assert "down" in body["error"]


# ---------------------------------------------------------------------------
# integrations/linkedin_routes.py
# ---------------------------------------------------------------------------

class TestLinkedInRoutes:
    def _call(self, method, path, svc, **kw):
        """Perform a request with get_linkedin_service patched for its duration."""
        from integrations.linkedin_routes import router

        with patch(
            "integrations.linkedin_routes.get_linkedin_service", return_value=svc
        ):
            resp = getattr(make_client(router, authed=True), method)(path, **kw)
        return resp

    def _call_unavailable(self, method, path, **kw):
        from integrations.linkedin_routes import router

        with patch("integrations.linkedin_routes.LINKEDIN_AVAILABLE", False):
            resp = getattr(make_client(router, authed=True), method)(path, **kw)
        return resp

    def _plain(self, method, path, **kw):
        from integrations.linkedin_routes import router

        return getattr(make_client(router, authed=True), method)(path, **kw)

    def test_linkedin_router_mounts(self):
        """REGRESSION: phantom get_linkedin_service factory -> LINKEDIN_AVAILABLE
        stuck False -> /profile permanently 501."""
        from integrations.linkedin_routes import LINKEDIN_AVAILABLE

        assert LINKEDIN_AVAILABLE is True
        resp = self._plain("get", "/api/linkedin/status")
        assert resp.status_code == 200
        assert resp.json()["available"] is True

    def test_linkedin_get_service_factory(self):
        from integrations.linkedin_routes import get_linkedin_service
        from integrations.linkedin_service import LinkedInService

        assert isinstance(get_linkedin_service(), LinkedInService)

    def test_auth_url_available(self):
        svc = _svc({})
        svc.get_authorization_url = MagicMock(return_value="https://li.example/auth?x=1")
        resp = self._call(
            "get", "/api/linkedin/auth/url", svc, params={"redirect_uri": "https://app/cb"}
        )
        assert resp.status_code == 200
        assert resp.json()["url"] == "https://li.example/auth?x=1"
        svc.get_authorization_url.assert_called_once_with("https://app/cb")

    def test_auth_url_default_redirect_uri(self):
        svc = _svc({})
        svc.get_authorization_url = MagicMock(return_value="https://li.example/auth")
        resp = self._call("get", "/api/linkedin/auth/url", svc)
        assert resp.status_code == 200
        svc.get_authorization_url.assert_called_once_with(
            "http://localhost:3000/integrations/linkedin/callback"
        )

    def test_auth_url_unavailable_mock(self):
        resp = self._call_unavailable(
            "get", "/api/linkedin/auth/url", params={"redirect_uri": "https://app/cb"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "INSERT_CLIENT_ID" in body["url"]
        assert "redirect_uri=https://app/cb" in body["url"]

    def test_callback_success(self):
        svc = _svc({"exchange_token": {"access_token": "li-tok"}})
        resp = self._call(
            "post",
            "/api/linkedin/callback",
            svc,
            json={"code": "auth-code", "redirect_uri": "https://app/cb"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["access_token"] == "li-tok"
        assert body["status"] == "success"
        svc.exchange_token.assert_awaited_once_with("auth-code", "https://app/cb")

    def test_callback_service_exception_400(self):
        svc = _svc({"exchange_token": ValueError("bad code")})
        resp = self._call(
            "post",
            "/api/linkedin/callback",
            svc,
            json={"code": "bad", "redirect_uri": "https://app/cb"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Internal error"

    def test_callback_unavailable_mock(self):
        resp = self._call_unavailable(
            "post",
            "/api/linkedin/callback",
            json={"code": "c", "redirect_uri": "https://app/cb"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "c"
        assert "mock" in body["message"]

    def test_callback_missing_fields_422(self):
        resp = self._plain("post", "/api/linkedin/callback", json={"code": "c"})
        assert resp.status_code == 422

    PROFILE = {
        "id": "abc123",
        "localizedFirstName": "Ada",
        "localizedLastName": "Lovelace",
        "profilePicture": {
            "displayImage~": {
                "elements": [{"identifiers": [{"identifier": "https://img.example/p"}]}]
            }
        },
        "headline": {"default": "Mathematician"},
    }

    def test_profile_success_full(self):
        svc = _svc({"get_profile": self.PROFILE})
        resp = self._call(
            "get", "/api/linkedin/profile", svc, params={"access_token": "li-tok"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "abc123"
        assert body["name"] == "Ada Lovelace"
        assert body["firstName"] == "Ada"
        assert body["lastName"] == "Lovelace"
        assert body["profilePicture"] == "https://img.example/p"
        assert body["headline"] == "Mathematician"
        svc.get_profile.assert_awaited_once_with("li-tok")

    def test_profile_success_minimal(self):
        svc = _svc({"get_profile": {"id": "x", "localizedFirstName": "Bob"}})
        resp = self._call(
            "get", "/api/linkedin/profile", svc, params={"access_token": "li-tok"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Bob"
        assert body["profilePicture"] is None
        assert body["headline"] is None

    @pytest.mark.parametrize("token", ["mock", "fake_token", ""])
    def test_profile_invalid_tokens_401(self, token):
        svc = _svc({"get_profile": self.PROFILE})
        resp = self._call(
            "get", "/api/linkedin/profile", svc, params={"access_token": token}
        )
        assert resp.status_code == 401
        assert "Invalid LinkedIn access token" in resp.json()["detail"]
        svc.get_profile.assert_not_awaited()

    def test_profile_missing_token_422(self):
        svc = _svc({"get_profile": self.PROFILE})
        resp = self._call("get", "/api/linkedin/profile", svc)
        assert resp.status_code == 422
        svc.get_profile.assert_not_awaited()

    def test_profile_unavailable_501(self):
        resp = self._call_unavailable(
            "get", "/api/linkedin/profile", params={"access_token": "tok"}
        )
        assert resp.status_code == 501

    def test_profile_service_exception_maps_to_400(self):
        """REGRESSION: except handler called undefined `logger` -> NameError ->
        500 instead of the intended 400."""
        svc = _svc({"get_profile": RuntimeError("api down")})
        resp = self._call(
            "get", "/api/linkedin/profile", svc, params={"access_token": "li-tok"}
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Internal error"

    def test_profile_http_exception_passthrough(self):
        from fastapi import HTTPException

        svc = _svc({})
        svc.get_profile = AsyncMock(
            side_effect=HTTPException(status_code=403, detail="Forbidden")
        )
        resp = self._call(
            "get", "/api/linkedin/profile", svc, params={"access_token": "li-tok"}
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Forbidden"

    def test_share_success(self):
        svc = _svc({"share_update": {"id": "urn:li:share:42"}})
        resp = self._call(
            "post",
            "/api/linkedin/share",
            svc,
            params={"access_token": "li-tok", "text": "Hello world"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["id"] == "urn:li:share:42"
        assert body["postUrn"] == "urn:li:share:42"
        assert body["status"] == "published"
        svc.share_update.assert_awaited_once_with("Hello world", "li-tok", "PUBLIC")

    def test_share_visibility_uppercased(self):
        svc = _svc({"share_update": {"id": "urn:1"}})
        resp = self._call(
            "post",
            "/api/linkedin/share",
            svc,
            params={"access_token": "li-tok", "text": "hi", "visibility": "connections"},
        )
        assert resp.status_code == 200
        svc.share_update.assert_awaited_once_with("hi", "li-tok", "CONNECTIONS")

    def test_share_container_visibility(self):
        svc = _svc({"share_update": {"id": "urn:2"}})
        resp = self._call(
            "post",
            "/api/linkedin/share",
            svc,
            params={"access_token": "li-tok", "text": "hi", "visibility": "CONTAINER"},
        )
        assert resp.status_code == 200
        svc.share_update.assert_awaited_once_with("hi", "li-tok", "CONTAINER")

    @pytest.mark.parametrize("text", ["", "   "])
    def test_share_empty_text_400(self, text):
        svc = _svc({"share_update": {"id": "urn"}})
        resp = self._call(
            "post",
            "/api/linkedin/share",
            svc,
            params={"access_token": "li-tok", "text": text},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Post content cannot be empty"
        svc.share_update.assert_not_awaited()

    def test_share_missing_text_422(self):
        svc = _svc({"share_update": {"id": "urn"}})
        resp = self._call(
            "post", "/api/linkedin/share", svc, params={"access_token": "li-tok"}
        )
        assert resp.status_code == 422
        svc.share_update.assert_not_awaited()

    def test_share_invalid_visibility_400(self):
        svc = _svc({"share_update": {"id": "urn"}})
        resp = self._call(
            "post",
            "/api/linkedin/share",
            svc,
            params={"access_token": "li-tok", "text": "hi", "visibility": "SECRET"},
        )
        assert resp.status_code == 400
        assert "Invalid visibility" in resp.json()["detail"]
        svc.share_update.assert_not_awaited()

    @pytest.mark.parametrize("token", ["mock", "fake_token", ""])
    def test_share_invalid_tokens_401(self, token):
        svc = _svc({"share_update": {"id": "urn"}})
        resp = self._call(
            "post",
            "/api/linkedin/share",
            svc,
            params={"access_token": token, "text": "hi"},
        )
        assert resp.status_code == 401

    def test_share_unavailable_501(self):
        resp = self._call_unavailable(
            "post",
            "/api/linkedin/share",
            params={"access_token": "li-tok", "text": "hi"},
        )
        assert resp.status_code == 501

    def test_share_service_exception_maps_to_400(self):
        """REGRESSION: except handler called undefined `logger` -> NameError ->
        500 instead of the intended 400."""
        svc = _svc({"share_update": RuntimeError("post failed")})
        resp = self._call(
            "post",
            "/api/linkedin/share",
            svc,
            params={"access_token": "li-tok", "text": "hi"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Internal error"

    def test_share_http_exception_passthrough(self):
        from fastapi import HTTPException

        svc = _svc({})
        svc.share_update = AsyncMock(
            side_effect=HTTPException(status_code=429, detail="rate limited")
        )
        resp = self._call(
            "post",
            "/api/linkedin/share",
            svc,
            params={"access_token": "li-tok", "text": "hi"},
        )
        assert resp.status_code == 429

    def test_status_available(self):
        with patch("integrations.linkedin_routes.LINKEDIN_AVAILABLE", True):
            resp = self._plain("get", "/api/linkedin/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["available"] is True
        assert body["status"] == "active"
        assert body["business_value"]["lead_generation"] is True

    def test_status_unavailable(self):
        resp = self._call_unavailable("get", "/api/linkedin/status")
        assert resp.status_code == 200
        assert resp.json()["available"] is False

    def test_health_available_returns_health(self):
        """REGRESSION: health_check is SYNC; `await` raised TypeError -> 500."""
        svc = _svc({})
        svc.health_check = MagicMock(
            return_value={"ok": True, "status": "healthy", "service": "linkedin"}
        )
        resp = self._call("get", "/api/linkedin/health", svc)
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"
        svc.health_check.assert_called_once()

    def test_health_unavailable_uses_status(self):
        resp = self._call_unavailable("get", "/api/linkedin/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "active"
        assert body["available"] is False


# ---------------------------------------------------------------------------
# core/sandbox_runtime/e2b_runner.py
# ---------------------------------------------------------------------------

class TestE2BRuntime:
    def test_is_available_no_key(self, monkeypatch):
        monkeypatch.delenv("E2B_API_KEY", raising=False)
        assert e2b_runner.is_available() is False

    def test_is_available_key_no_sdk(self, monkeypatch):
        monkeypatch.setenv("E2B_API_KEY", "fake-key")
        assert e2b_runner.is_available() is False

    def test_is_available_key_and_sdk(self, monkeypatch):
        monkeypatch.setenv("E2B_API_KEY", "fake-key")
        with patch.dict(sys.modules, {"e2b": MagicMock()}):
            assert e2b_runner.is_available() is True

    def test_constructor_initial_state(self):
        runtime = e2b_runner.E2BRuntime()
        assert runtime._client is None
        assert isinstance(runtime._init_lock, asyncio.Lock)

    def test_ensure_client_creates_once(self, monkeypatch):
        monkeypatch.setenv("E2B_API_KEY", "fake-key")
        fake_sandbox = MagicMock()
        sandbox_inst = MagicMock()
        fake_sandbox.Sandbox.return_value = sandbox_inst
        runtime = e2b_runner.E2BRuntime()
        with patch.dict(sys.modules, {"e2b": fake_sandbox}):
            client1 = asyncio.run(runtime._ensure_client())
            client2 = asyncio.run(runtime._ensure_client())
        assert client1 is sandbox_inst
        assert client2 is sandbox_inst
        fake_sandbox.Sandbox.assert_called_once_with()

    def test_execute_python_unavailable(self, monkeypatch):
        monkeypatch.delenv("E2B_API_KEY", raising=False)
        runtime = e2b_runner.E2BRuntime()
        result = asyncio.run(runtime.execute_python("print(1)", policy=_policy()))
        assert isinstance(result, SandboxExecResult)
        assert result.success is False
        assert result.exit_code == -1
        assert "E2B_API_KEY" in result.stderr
        assert result.metadata["reason"] == "unavailable"

    def test_execute_python_success(self, monkeypatch):
        monkeypatch.setenv("E2B_API_KEY", "fake-key")
        fake_client = MagicMock()
        fake_client.run = MagicMock(
            return_value=SimpleNamespace(stdout="hello\n", stderr="", exit_code=0)
        )
        runtime = e2b_runner.E2BRuntime()
        with patch.object(
            e2b_runner, "is_available", return_value=True
        ), patch.object(
            e2b_runner.E2BRuntime, "_ensure_client",
            new=AsyncMock(return_value=fake_client),
        ), patch.object(
            e2b_runner.asyncio, "to_thread",
            new=AsyncMock(side_effect=lambda fn, *a, **k: fn(*a, **k)),
        ):
            result = asyncio.run(
                runtime.execute_python("print('hi')", policy=_policy(max_exec_seconds=10))
            )
        assert result.success is True
        assert result.stdout == "hello\n"
        assert result.exit_code == 0
        assert result.metadata == {"backend": "e2b"}
        fake_client.run.assert_called_once_with("print('hi')", language="python", timeout=10)

    def test_execute_python_timeout_clamped(self, monkeypatch):
        monkeypatch.setenv("E2B_API_KEY", "fake-key")
        fake_client = MagicMock()
        fake_client.run = MagicMock(
            return_value=SimpleNamespace(stdout="", stderr="", exit_code=0)
        )
        runtime = e2b_runner.E2BRuntime()
        with patch.object(
            e2b_runner, "is_available", return_value=True
        ), patch.object(
            e2b_runner.E2BRuntime, "_ensure_client",
            new=AsyncMock(return_value=fake_client),
        ), patch.object(
            e2b_runner.asyncio, "to_thread",
            new=AsyncMock(side_effect=lambda fn, *a, **k: fn(*a, **k)),
        ):
            result = asyncio.run(
                runtime.execute_python("x", policy=_policy(max_exec_seconds=-5))
            )
        assert result.success is True
        fake_client.run.assert_called_once_with("x", language="python", timeout=1)

    def test_execute_python_default_timeout_and_none_policy(self, monkeypatch):
        monkeypatch.setenv("E2B_API_KEY", "fake-key")
        fake_client = MagicMock()
        fake_client.run = MagicMock(
            return_value=SimpleNamespace(stdout="", stderr="", exit_code=0)
        )
        runtime = e2b_runner.E2BRuntime()
        with patch.object(
            e2b_runner, "is_available", return_value=True
        ), patch.object(
            e2b_runner.E2BRuntime, "_ensure_client",
            new=AsyncMock(return_value=fake_client),
        ), patch.object(
            e2b_runner.asyncio, "to_thread",
            new=AsyncMock(side_effect=lambda fn, *a, **k: fn(*a, **k)),
        ):
            result = asyncio.run(runtime.execute_python("x", policy=None))
        assert result.success is True
        fake_client.run.assert_called_once_with("x", language="python", timeout=30)

    def test_execute_python_exception(self, monkeypatch):
        monkeypatch.setenv("E2B_API_KEY", "fake-key")
        fake_client = MagicMock()
        runtime = e2b_runner.E2BRuntime()
        with patch.object(
            e2b_runner, "is_available", return_value=True
        ), patch.object(
            e2b_runner.E2BRuntime, "_ensure_client",
            new=AsyncMock(return_value=fake_client),
        ), patch.object(
            e2b_runner.asyncio, "to_thread",
            new=AsyncMock(side_effect=RuntimeError("sandbox died")),
        ):
            result = asyncio.run(runtime.execute_python("x", policy=_policy()))
        assert result.success is False
        assert result.exit_code == -1
        assert "E2B runtime error: sandbox died" in result.stderr
        assert result.metadata["error"] == "sandbox died"

    def test_execute_command_unavailable(self, monkeypatch):
        monkeypatch.delenv("E2B_API_KEY", raising=False)
        runtime = e2b_runner.E2BRuntime()
        result = asyncio.run(runtime.execute_command("ls", policy=_policy()))
        assert result.success is False
        assert result.metadata["reason"] == "unavailable"

    def test_execute_command_success(self, monkeypatch):
        monkeypatch.setenv("E2B_API_KEY", "fake-key")
        fake_client = MagicMock()
        fake_client.commands.run = MagicMock(
            return_value=SimpleNamespace(stdout="out", stderr="", exit_code=0)
        )
        runtime = e2b_runner.E2BRuntime()
        with patch.object(
            e2b_runner, "is_available", return_value=True
        ), patch.object(
            e2b_runner.E2BRuntime, "_ensure_client",
            new=AsyncMock(return_value=fake_client),
        ), patch.object(
            e2b_runner.asyncio, "to_thread",
            new=AsyncMock(side_effect=lambda fn, *a, **k: fn(*a, **k)),
        ):
            result = asyncio.run(
                runtime.execute_command("ls -la", policy=_policy(max_exec_seconds=5))
            )
        assert result.success is True
        assert result.stdout == "out"
        fake_client.commands.run.assert_called_once_with("ls -la", timeout=5)

    def test_execute_command_exception(self, monkeypatch):
        monkeypatch.setenv("E2B_API_KEY", "fake-key")
        fake_client = MagicMock()
        runtime = e2b_runner.E2BRuntime()
        with patch.object(
            e2b_runner, "is_available", return_value=True
        ), patch.object(
            e2b_runner.E2BRuntime, "_ensure_client",
            new=AsyncMock(return_value=fake_client),
        ), patch.object(
            e2b_runner.asyncio, "to_thread",
            new=AsyncMock(side_effect=TimeoutError("timed out")),
        ):
            result = asyncio.run(runtime.execute_command("ls", policy=_policy()))
        assert result.success is False
        assert "timed out" in result.stderr

    def test_cleanup_no_client(self):
        runtime = e2b_runner.E2BRuntime()
        assert asyncio.run(runtime.cleanup()) is None
        assert runtime._client is None

    def test_cleanup_kills_client(self):
        fake_client = MagicMock()
        fake_client.kill = MagicMock()
        runtime = e2b_runner.E2BRuntime()
        runtime._client = fake_client
        asyncio.run(runtime.cleanup())
        fake_client.kill.assert_called_once()
        assert runtime._client is None

    def test_cleanup_kill_exception_swallowed(self):
        fake_client = MagicMock()
        fake_client.kill = MagicMock(side_effect=RuntimeError("kill failed"))
        runtime = e2b_runner.E2BRuntime()
        runtime._client = fake_client
        asyncio.run(runtime.cleanup())
        assert runtime._client is None

    def test_parse_result_full(self):
        result = e2b_runner._parse_e2b_result(
            SimpleNamespace(stdout="out", stderr="err", exit_code=2)
        )
        assert result.success is False
        assert result.stdout == "out"
        assert result.stderr == "err"
        assert result.exit_code == 2
        assert result.truncated is False
        assert result.metadata == {"backend": "e2b"}

    def test_parse_result_text_fallback(self):
        result = e2b_runner._parse_e2b_result(SimpleNamespace(text="text-out", stderr=""))
        assert result.stdout == "text-out"
        assert result.success is True

    def test_parse_result_returncode_fallback(self):
        result = e2b_runner._parse_e2b_result(SimpleNamespace(stderr="e", returncode=1))
        assert result.success is False
        assert result.exit_code == 1
        assert result.stdout == ""

    def test_parse_result_truncation(self):
        result = e2b_runner._parse_e2b_result(
            SimpleNamespace(stdout="x" * 70000, stderr="y" * 70000, exit_code=0)
        )
        assert result.success is True
        assert len(result.stdout) == 65536
        assert len(result.stderr) == 65536
        assert result.truncated is True

    def test_parse_result_bare_object_defaults(self):
        result = e2b_runner._parse_e2b_result(SimpleNamespace())
        assert result.success is True
        assert result.stdout == ""
        assert result.stderr == ""
        assert result.exit_code == 0
