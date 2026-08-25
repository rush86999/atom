"""
Regression tests for the Greptile P1 on PR #591 (review 4996183494):
"Session ownership checks become optional" in integrations/chat_routes.py.

The regression: rename / details / history took
``Optional[User] = Depends(get_optional_current_user)`` and guarded ownership
with ``if current_user and not _ensure_session_access(...)`` — so when the
optional dependency resolved to None (or to its dev-mode fallback: the FIRST
ACTIVE USER IN THE DATABASE, core/auth.py:214), the guard was skipped or the
caller silently impersonated that user. Legacy ``default_user``-owned
sessions made the reclaim path exploitable end-to-end.

Pins:
  - source: the three session routes must NOT depend on
    get_optional_current_user (mandatory auth only).
  - behavior with an unresolvable optional user (None): every route must
    reject (401/403) — never 200. Under the regressed code these returned
    200 because the ownership guard was skipped entirely.
"""

import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security_dependencies import get_current_user
from integrations import chat_routes as cr

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

FLAGGED_ROUTES = [
    ("PATCH", "/api/chat/sessions/s1"),
    ("GET", "/api/chat/sessions/s1"),
    ("GET", "/api/chat/history/s1"),
]


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(cr.router)
    return application


@pytest.fixture
def anon_client(app):
    return TestClient(app)


@pytest.fixture
def client(app):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="user_1", tenant_id="t1")
    return TestClient(app)


@pytest.fixture
def orch():
    with patch.object(cr, "chat_orchestrator") as m:
        m.session_manager = MagicMock()
        yield m


def make_session(session_id="s1", owner="other_user", history=None):
    return {
        "id": session_id,
        "session_id": session_id,
        "user_id": owner,
        "title": "Someone else's chat",
        "created_at": "2026-01-01T00:00:00",
        "last_updated": "2026-01-01T00:00:00",
        "history": history or [{"role": "user", "content": "secret"}],
        "context": {},
    }


class TestNoOptionalAuthOnSessionRoutes:
    def test_flagged_routes_use_mandatory_auth(self):
        """Greptile P1 pin: rename/details/history must authenticate
        mandatorily — get_optional_current_user's dev fallback (first active
        user) turns 'no auth' into silent impersonation."""
        for method, path in FLAGGED_ROUTES:
            for route in cr.router.routes:
                if getattr(route, "path", "") == path and method in getattr(
                    route, "methods", set()
                ):
                    src = inspect.getsource(route.endpoint)
                    assert "get_optional_current_user" not in src, (
                        f"{method} {path} must not use optional auth"
                    )
                    assert "Depends(get_current_user)" in src or (
                        "current_user" in src
                    )

    def test_module_still_exports_helper(self):
        # the helper itself is fine for genuinely-public surfaces; only the
        # session-ownership routes were wrong.
        assert hasattr(cr, "_ensure_session_access")


class TestUnresolvableUserMustReject:
    """With the optional dependency resolving to None (expired/invalid token
    under any future regression), routes must reject — never serve content.

    Under the REGRESSED code these three requests returned 200: the
    ``if current_user and ...`` guard skipped ownership entirely and the
    details route had none at all.
    """

    def test_unauthenticated_never_gets_content(self, anon_client, orch):
        """No token at all: the mandatory dependency must 401 BEFORE any
        ownership logic. Under the REGRESSED code (optional auth + skipped
        guards) rename/details/history returned 200 for another user's
        session."""
        orch.conversation_sessions = {"s1": make_session(owner="other_user")}
        for method, path in FLAGGED_ROUTES:
            kwargs = (
                {"json": {"title": "hijacked", "user_id": "x"}}
                if method == "PATCH"
                else {"params": {"user_id": "x"}}
            )
            resp = getattr(anon_client, method.lower())(path, **kwargs)
            assert resp.status_code in (401, 403), (
                f"{method} {path} served content unauthenticated: "
                f"{resp.status_code} {resp.text[:120]}"
            )
            assert resp.status_code != 200


class TestCrossUserOwnershipEnforced:
    def test_details_cross_user_denied(self, client, orch):
        """Greptile: 'the details route performs no ownership check at all'."""
        orch.conversation_sessions = {"s1": make_session(owner="other_user")}
        resp = client.get("/api/chat/sessions/s1", params={"user_id": "u"})
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Access denied"

    def test_history_cross_user_denied(self, client, orch):
        orch.conversation_sessions = {"s1": make_session(
            owner="other_user",
            history=[{"role": "user", "content": "private payload"}],
        )}
        resp = client.get("/api/chat/history/s1", params={"user_id": "u"})
        assert resp.status_code == 403
        assert "private payload" not in resp.text

    def test_rename_cross_user_denied(self, client, orch):
        orch.conversation_sessions = {"s1": make_session(owner="other_user")}
        resp = client.patch("/api/chat/sessions/s1",
                            json={"title": "hijack", "user_id": "u"})
        assert resp.status_code == 403
        assert orch.rename_session.assert_not_called() is None