"""
Coverage-push for api/browser_routes.py error paths.

Targets the five uncovered branches:
- _check_browser_governance exception swallow (156-157)
- _create_browser_audit exception swallow (202-204)
- navigate DB session update failure (370-371)
- fill-form non-submit governance action branch (449)
- close_session DB session update failure (685-686)
"""
import os
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

os.environ["TESTING"] = "1"

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.models import AgentRegistry, AgentStatus, User
from tests.factories.user_factory import AdminUserFactory


class FailingCommitSession:
    """Session proxy that raises on commit (DB failure simulation)."""

    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        if name == "commit":
            raise RuntimeError("database commit failed")
        return getattr(self._inner, name)


@pytest.fixture(scope="function")
def client(db_session: Session):
    """TestClient with dependency overrides (same pattern as the main suite)."""
    from main_api_app import app
    from core.auth import get_current_user
    from core.database import get_db

    def _get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db

    auth_user = {}

    def _mock_get_current_user():
        if "user" not in auth_user:
            unique_id = str(uuid.uuid4())[:8]
            email = f"test_{unique_id}@browser.com"
            try:
                user = db_session.query(User).filter(User.email == email).first()
            except Exception:
                user = None
            if not user:
                user = AdminUserFactory(email=email, _session=db_session)
                db_session.commit()
                db_session.refresh(user)
            auth_user["user"] = user
        return auth_user["user"]

    try:
        app.dependency_overrides[get_current_user] = _mock_get_current_user
    except (ImportError, AttributeError):
        pass

    for middleware in app.user_middleware:
        if hasattr(middleware, 'cls') and middleware.cls.__name__ == 'TrustedHostMiddleware':
            middleware.kwargs['allowed_hosts'] = ['testserver', 'localhost', '127.0.0.1', '0.0.0.0', '*']
            break

    test_client = TestClient(app, base_url="http://testserver")
    test_client.headers.update(
        {"X-Test-Secret": os.getenv("E2E_TEST_SECRET", "test-secret-key")}
    )

    yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def intern_agent(db_session: Session):
    agent = AgentRegistry(
        name="InternCovBrowserAgent",
        category="test",
        module_path="test.module",
        class_name="InternCovBrowser",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6,
        workspace_id="default",
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def mock_tool_functions():
    with patch("api.browser_routes.browser_create_session", new_callable=AsyncMock) as mock_create, \
            patch("api.browser_routes.browser_navigate", new_callable=AsyncMock) as mock_navigate, \
            patch("api.browser_routes.browser_screenshot", new_callable=AsyncMock) as mock_screenshot, \
            patch("api.browser_routes.browser_click", new_callable=AsyncMock) as mock_click, \
            patch("api.browser_routes.browser_fill_form", new_callable=AsyncMock) as mock_fill, \
            patch("api.browser_routes.browser_extract_text", new_callable=AsyncMock) as mock_extract, \
            patch("api.browser_routes.browser_execute_script", new_callable=AsyncMock) as mock_script, \
            patch("api.browser_routes.browser_close_session", new_callable=AsyncMock) as mock_close, \
            patch("api.browser_routes.browser_get_page_info", new_callable=AsyncMock) as mock_info:
        mock_create.return_value = {
            "success": True,
            "session_id": str(uuid.uuid4()),
            "browser_type": "chromium",
            "headless": True,
            "created_at": datetime.now().isoformat(),
        }
        mock_navigate.return_value = {
            "success": True,
            "url": "https://example.com",
            "title": "Example Domain",
            "status": 200,
            "timestamp": datetime.now().isoformat(),
        }
        mock_screenshot.return_value = {
            "success": True, "data": "base64data", "size_bytes": 12345, "format": "png",
        }
        mock_click.return_value = {"success": True, "session_id": "s1", "selector": "#b"}
        mock_fill.return_value = {"success": True, "fields_filled": 2, "submitted": False}
        mock_extract.return_value = {"success": True, "text": "hello", "length": 5}
        mock_script.return_value = {"success": True, "result": "ok"}
        mock_close.return_value = {"success": True, "session_id": "s1"}
        mock_info.return_value = {
            "success": True, "session_id": "s1", "title": "T", "url": "https://example.com",
        }
        yield {
            "create": mock_create, "navigate": mock_navigate,
            "screenshot": mock_screenshot, "click": mock_click,
            "fill": mock_fill, "extract": mock_extract,
            "script": mock_script, "close": mock_close, "info": mock_info,
        }


def _create_session(client):
    response = client.post(
        "/api/browser/session/create",
        json={"browser_type": "chromium", "headless": True},
    )
    assert response.status_code == 200
    return response.json()["session_id"]


class TestGovernanceExceptionPath:

    def test_screenshot_governance_failure_is_swallowed(
        self, client, mock_tool_functions, intern_agent
    ):
        with patch("api.browser_routes.AgentContextResolver") as mock_resolver_cls:
            mock_resolver_cls.return_value.resolve_agent_for_request = AsyncMock(
                side_effect=RuntimeError("resolver boom")
            )
            response = client.post(
                "/api/browser/screenshot",
                json={
                    "session_id": "s1",
                    "full_page": False,
                    "agent_id": intern_agent.id,
                },
            )
        assert response.status_code == 200
        assert response.json()["success"] is True


class TestAuditFailurePath:

    def test_click_audit_failure_is_best_effort(
        self, client, mock_tool_functions
    ):
        with patch("api.browser_routes.BrowserAudit", side_effect=RuntimeError("audit boom")):
            response = client.post(
                "/api/browser/click",
                json={"session_id": "s1", "selector": "#b"},
            )
        assert response.status_code == 200
        assert response.json()["success"] is True


class TestNavigateDbUpdateFailure:

    def test_navigate_survives_db_commit_failure(
        self, client, mock_tool_functions, db_session
    ):
        from core.auth import get_current_user
        from core.database import get_db

        session_id = _create_session(client)

        def _failing_db():
            try:
                yield FailingCommitSession(db_session)
            finally:
                pass

        client.app.dependency_overrides[get_db] = _failing_db
        response = client.post(
            "/api/browser/navigate",
            json={"session_id": session_id, "url": "https://example.com"},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True


class TestFillFormNonSubmitBranch:

    def test_fill_form_without_submit_with_agent(
        self, client, mock_tool_functions, intern_agent
    ):
        response = client.post(
            "/api/browser/fill-form",
            json={
                "session_id": "s1",
                "selectors": {"#name": "John"},
                "submit": False,
                "agent_id": intern_agent.id,
            },
        )
        assert response.status_code == 200
        assert response.json()["success"] is True


class TestCloseSessionDbUpdateFailure:

    def test_close_session_survives_db_commit_failure(
        self, client, mock_tool_functions, db_session
    ):
        from core.database import get_db

        session_id = _create_session(client)

        def _failing_db():
            try:
                yield FailingCommitSession(db_session)
            finally:
                pass

        client.app.dependency_overrides[get_db] = _failing_db
        response = client.post(
            "/api/browser/session/close",
            json={"session_id": session_id},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
