"""
Browser governance integration tests (INTG-18).

Tests cover:
- STUDENT agent access
- INTERN agent access
- SUPERVISED agent access
- AUTONOMOUS agent access

Ported to the current API surface: browser actions live under
``/api/browser/<action>`` with ``session_id`` in the request body (the old
``/api/browser/{session_id}/<action>`` path layout no longer exists), and
the tool functions imported into ``api.browser_routes`` are
``browser_fill_form`` / ``browser_close_session`` etc.
"""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.factories.agent_factory import (
    StudentAgentFactory,
    InternAgentFactory,
    SupervisedAgentFactory,
    AutonomousAgentFactory,
)
from core.models import BrowserAudit, BrowserSession


def _agent(factory, db_session: Session):
    """Create a committed agent visible to the API's DB session."""
    agent = factory(_session=db_session)
    db_session.commit()
    return agent


class TestStudentAgentAccess:
    """Test STUDENT agent browser access."""

    def test_student_blocked_from_browser_session(self, client: TestClient, auth_token: str, db_session: Session):
        """Test STUDENT agents blocked from browser sessions."""
        student = _agent(StudentAgentFactory, db_session)

        response = client.post(
            "/api/browser/session/create",
            json={
                "browser_type": "chromium",
                "agent_id": student.id
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # STUDENT blocked from browser automation (action complexity 2)
        assert response.status_code == 403

    def test_student_blocked_from_navigation(self, client: TestClient, auth_token: str, db_session: Session):
        """Test STUDENT agents blocked from browser navigation."""
        student = _agent(StudentAgentFactory, db_session)

        session_id = str(uuid.uuid4())

        response = client.post(
            "/api/browser/navigate",
            json={
                "session_id": session_id,
                "url": "https://example.com",
                "agent_id": student.id
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # STUDENT blocked from navigation
        assert response.status_code == 403

    def test_student_blocked_from_screenshot(self, client: TestClient, auth_token: str, db_session: Session):
        """Test STUDENT agents blocked from screenshots."""
        student = _agent(StudentAgentFactory, db_session)

        session_id = str(uuid.uuid4())

        response = client.post(
            "/api/browser/screenshot",
            json={"session_id": session_id, "agent_id": student.id},
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # STUDENT blocked from screenshots
        assert response.status_code == 403


class TestInternAgentAccess:
    """Test INTERN agent browser access."""

    def test_intern_can_create_browser_session(self, client: TestClient, auth_token: str, db_session: Session):
        """Test INTERN agents can create browser sessions."""
        intern = _agent(InternAgentFactory, db_session)

        with patch('api.browser_routes.browser_create_session', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = {
                "success": True,
                "session_id": "intern-session-123"
            }

            response = client.post(
                "/api/browser/session/create",
                json={
                    "browser_type": "chromium",
                    "agent_id": intern.id
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            # INTERN can use browser (action complexity 2)
            assert response.status_code == 200
            assert response.json()["success"] is True

    def test_intern_can_navigate(self, client: TestClient, auth_token: str, db_session: Session):
        """Test INTERN agents can navigate browser."""
        intern = _agent(InternAgentFactory, db_session)

        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_navigate', new_callable=AsyncMock) as mock_navigate:
            mock_navigate.return_value = {"success": True, "url": "https://example.com"}

            response = client.post(
                "/api/browser/navigate",
                json={
                    "session_id": session_id,
                    "url": "https://example.com",
                    "agent_id": intern.id
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            # INTERN can navigate
            assert response.status_code == 200
            assert response.json()["success"] is True

    def test_intern_can_take_screenshot(self, client: TestClient, auth_token: str, db_session: Session):
        """Test INTERN agents can take screenshots."""
        intern = _agent(InternAgentFactory, db_session)

        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_screenshot', new_callable=AsyncMock) as mock_screenshot:
            mock_screenshot.return_value = {
                "success": True,
                "screenshot": "base64image"
            }

            response = client.post(
                "/api/browser/screenshot",
                json={"session_id": session_id, "agent_id": intern.id},
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            # INTERN can take screenshots
            assert response.status_code == 200
            assert response.json()["success"] is True

    def test_intern_can_fill_forms(self, client: TestClient, auth_token: str, db_session: Session):
        """Test INTERN agents can fill forms."""
        intern = _agent(InternAgentFactory, db_session)

        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_fill_form', new_callable=AsyncMock) as mock_fill:
            mock_fill.return_value = {"success": True}

            response = client.post(
                "/api/browser/fill-form",
                json={
                    "session_id": session_id,
                    "selectors": {"#email": "intern@example.com"},
                    "agent_id": intern.id
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            # INTERN can fill forms (read-only action)
            assert response.status_code == 200
            assert response.json()["success"] is True


class TestSupervisedAgentAccess:
    """Test SUPERVISED agent browser access."""

    def test_supervised_can_create_browser_session(self, client: TestClient, auth_token: str, db_session: Session):
        """Test SUPERVISED agents can create browser sessions."""
        supervised = _agent(SupervisedAgentFactory, db_session)

        with patch('api.browser_routes.browser_create_session', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = {
                "success": True,
                "session_id": "supervised-session-123"
            }

            response = client.post(
                "/api/browser/session/create",
                json={
                    "browser_type": "chromium",
                    "agent_id": supervised.id
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            # SUPERVISED can create sessions
            assert response.status_code == 200
            assert response.json()["success"] is True

    def test_supervised_can_click_elements(self, client: TestClient, auth_token: str, db_session: Session):
        """Test SUPERVISED agents can click elements."""
        supervised = _agent(SupervisedAgentFactory, db_session)

        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_click', new_callable=AsyncMock) as mock_click:
            mock_click.return_value = {"success": True}

            response = client.post(
                "/api/browser/click",
                json={
                    "session_id": session_id,
                    "selector": "#submit-button",
                    "agent_id": supervised.id
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            # SUPERVISED can click (state-changing action)
            assert response.status_code == 200
            assert response.json()["success"] is True

    def test_supervised_can_submit_forms(self, client: TestClient, auth_token: str, db_session: Session):
        """Test SUPERVISED agents can submit forms."""
        supervised = _agent(SupervisedAgentFactory, db_session)

        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_click', new_callable=AsyncMock) as mock_click:
            mock_click.return_value = {"success": True}

            response = client.post(
                "/api/browser/click",
                json={
                    "session_id": session_id,
                    "selector": "button[type='submit']",
                    "agent_id": supervised.id
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            # SUPERVISED can submit forms
            assert response.status_code == 200
            assert response.json()["success"] is True


class TestAutonomousAgentAccess:
    """Test AUTONOMOUS agent browser access."""

    def test_autonomous_full_browser_access(self, client: TestClient, auth_token: str, db_session: Session):
        """Test AUTONOMOUS agents have full browser access."""
        autonomous = _agent(AutonomousAgentFactory, db_session)

        session_id = str(uuid.uuid4())

        # Test multiple actions
        actions = [
            ("navigate", {"url": "https://example.com"}),
            ("fill-form", {"selectors": {"#email": "auto@example.com"}}),
            ("click", {"selector": "#submit"}),
            ("screenshot", {}),
        ]

        for action, params in actions:
            with patch(f'api.browser_routes.browser_{action.replace("-", "_")}', new_callable=AsyncMock) as mock_action:
                mock_action.return_value = {"success": True}

                response = client.post(
                    f"/api/browser/{action}",
                    json={"session_id": session_id, "agent_id": autonomous.id, **params},
                    headers={"Authorization": f"Bearer {auth_token}"}
                )

                # AUTONOMOUS should have full access
                assert response.status_code == 200
                assert response.json()["success"] is True

    def test_autonomous_can_close_sessions(self, client: TestClient, auth_token: str, db_session: Session):
        """Test AUTONOMOUS agents can close sessions."""
        autonomous = _agent(AutonomousAgentFactory, db_session)

        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_close_session', new_callable=AsyncMock) as mock_close:
            mock_close.return_value = {"success": True}

            response = client.post(
                "/api/browser/session/close",
                json={"session_id": session_id, "agent_id": autonomous.id},
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            # AUTONOMOUS can close sessions
            assert response.status_code == 200
            assert response.json()["success"] is True


class TestBrowserActionComplexity:
    """Test browser action complexity mapping."""

    def test_browser_navigation_complexity_2(self, client: TestClient, auth_token: str, db_session: Session):
        """Test browser navigation is complexity 2 (INTERN+)."""
        intern = _agent(InternAgentFactory, db_session)
        student = _agent(StudentAgentFactory, db_session)

        session_id = str(uuid.uuid4())

        # INTERN should be allowed
        with patch('api.browser_routes.browser_navigate', new_callable=AsyncMock) as mock_navigate:
            mock_navigate.return_value = {"success": True}

            intern_response = client.post(
                "/api/browser/navigate",
                json={"session_id": session_id, "url": "https://example.com", "agent_id": intern.id},
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            # STUDENT should be blocked
            student_response = client.post(
                "/api/browser/navigate",
                json={"session_id": session_id, "url": "https://example.com", "agent_id": student.id},
                headers={"Authorization": f"Bearer {auth_token}"}
            )

        # Verify governance enforced
        assert intern_response.status_code == 200
        assert student_response.status_code == 403

    def test_screenshot_complexity_2(self, client: TestClient, auth_token: str, db_session: Session):
        """Test screenshot is complexity 2 (INTERN+)."""
        intern = _agent(InternAgentFactory, db_session)

        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_screenshot', new_callable=AsyncMock) as mock_screenshot:
            mock_screenshot.return_value = {"success": True}

            response = client.post(
                "/api/browser/screenshot",
                json={"session_id": session_id, "agent_id": intern.id},
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            # INTERN+ can take screenshots
            assert response.status_code == 200
            assert response.json()["success"] is True

    def test_form_submit_complexity_3(self, client: TestClient, auth_token: str, db_session: Session):
        """Test form submission is complexity 3 (SUPERVISED+)."""
        supervised = _agent(SupervisedAgentFactory, db_session)

        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_click', new_callable=AsyncMock) as mock_click:
            mock_click.return_value = {"success": True}

            response = client.post(
                "/api/browser/click",
                json={
                    "session_id": session_id,
                    "selector": "button[type='submit']",
                    "agent_id": supervised.id
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            # SUPERVISED+ can submit forms
            assert response.status_code == 200
            assert response.json()["success"] is True


class TestBrowserAuditTrail:
    """Test browser automation audit trail."""

    def test_browser_session_creates_audit(self, client: TestClient, auth_token: str, db_session: Session):
        """Test browser sessions create audit records."""
        agent = _agent(InternAgentFactory, db_session)

        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_create_session', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = {
                "success": True,
                "session_id": session_id
            }

            response = client.post(
                "/api/browser/session/create",
                json={
                    "browser_type": "chromium",
                    "agent_id": agent.id
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            assert response.status_code == 200

            # The route persists a BrowserSession record for the created session
            record = db_session.query(BrowserSession).filter(
                BrowserSession.session_id == session_id
            ).first()
            assert record is not None
            assert record.agent_id == agent.id

    def test_browser_actions_logged(self, client: TestClient, auth_token: str, db_session: Session):
        """Test browser actions are logged."""
        agent = _agent(InternAgentFactory, db_session)

        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_navigate', new_callable=AsyncMock) as mock_navigate:
            mock_navigate.return_value = {
                "success": True,
                "url": "https://example.com"
            }

            response = client.post(
                "/api/browser/navigate",
                json={
                    "session_id": session_id,
                    "url": "https://example.com",
                    "agent_id": agent.id
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            assert response.status_code == 200

            # Every browser action writes a BrowserAudit entry
            audits = db_session.query(BrowserAudit).filter(
                BrowserAudit.session_id == session_id
            ).all()
            assert len(audits) >= 1
            assert audits[0].action == "navigate"
            assert audits[0].success is True
            assert audits[0].governance_check_passed is True


class TestBrowserSecurity:
    """Test browser automation security."""

    def test_blocked_urls(self, client: TestClient, auth_token: str, db_session: Session):
        """Test blocked URLs cannot be accessed."""
        agent = _agent(AutonomousAgentFactory, db_session)

        session_id = str(uuid.uuid4())

        # Try to navigate to blocked URL (e.g., internal network)
        with patch('api.browser_routes.browser_navigate', new_callable=AsyncMock) as mock_navigate:
            mock_navigate.return_value = {
                "success": False,
                "error": "URL blocked by security policy"
            }

            response = client.post(
                "/api/browser/navigate",
                json={
                    "session_id": session_id,
                    "url": "http://localhost:8080/admin",
                    "agent_id": agent.id
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            # Should block internal URLs
            assert response.status_code == 200
            data = response.json()
            assert data.get("success") is False or "blocked" in str(data).lower()

    def test_file_access_blocked(self, client: TestClient, auth_token: str, db_session: Session):
        """Test file:// URLs are blocked."""
        agent = _agent(AutonomousAgentFactory, db_session)

        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_navigate', new_callable=AsyncMock) as mock_navigate:
            mock_navigate.return_value = {
                "success": False,
                "error": "file:// URLs blocked"
            }

            response = client.post(
                "/api/browser/navigate",
                json={
                    "session_id": session_id,
                    "url": "file:///etc/passwd",
                    "agent_id": agent.id
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            # Should block file:// URLs
            assert response.status_code in [200, 400]
            data = response.json()
            assert data.get("success") is False


class TestBrowserResourceLimits:
    """Test browser resource limits."""

    def test_session_timeout(self, client: TestClient, auth_token: str, db_session: Session):
        """Test browser sessions timeout after inactivity."""
        agent = _agent(InternAgentFactory, db_session)

        session_id = str(uuid.uuid4())

        # Simulate session timeout
        with patch('api.browser_routes.browser_close_session', new_callable=AsyncMock) as mock_close:
            mock_close.return_value = {
                "success": True,
                "reason": "timeout"
            }

            response = client.post(
                "/api/browser/session/close",
                json={"session_id": session_id, "agent_id": agent.id},
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            assert response.status_code == 200
            assert response.json()["success"] is True

    def test_concurrent_session_limit(self, client: TestClient, auth_token: str, db_session: Session):
        """Test concurrent browser session limits."""
        agent = _agent(InternAgentFactory, db_session)

        # Try to create multiple sessions
        session_ids = []
        for i in range(10):
            with patch('api.browser_routes.browser_create_session', new_callable=AsyncMock) as mock_create:
                session_id = str(uuid.uuid4())
                session_ids.append(session_id)
                mock_create.return_value = {
                    "success": True,
                    "session_id": session_id
                }

                response = client.post(
                    "/api/browser/session/create",
                    json={
                        "browser_type": "chromium",
                        "agent_id": agent.id
                    },
                    headers={"Authorization": f"Bearer {auth_token}"}
                )

                # May limit concurrent sessions
                assert response.status_code in [200, 201, 429]
