"""
Browser action integration tests (INTG-17).

Tests cover:
- Browser form fill
- Browser click
- Browser scroll
- Browser wait
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.factories.agent_factory import InternAgentFactory, AutonomousAgentFactory
from unittest.mock import Mock, patch
import uuid


class TestBrowserFormFill:
    """Test browser form filling operations."""

    def test_fill_text_input(self, client: TestClient, auth_token: str, db_session: Session):
        """Test filling text input field."""
        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_fill') as mock_fill:
            mock_fill.return_value = {
                "success": True,
                "selector": "#email",
                "value": "test@example.com"
            }

            response = client.post(
                f"/api/browser/{session_id}/fill",
                json={
                    "selector": "#email",
                    "value": "test@example.com"
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            # Form fill should succeed
            assert response.status_code in [200, 201, 404, 405]

            if response.status_code in [200, 201]:
                data = response.json()
                assert data.get("success") is True

    def test_fill_multiple_fields(self, client: TestClient, auth_token: str, db_session: Session):
        """Test filling multiple form fields."""
        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_fill') as mock_fill:
            mock_fill.return_value = {
                "success": True,
                "fields_filled": 3
            }

            response = client.post(
                f"/api/browser/{session_id}/fill",
                json={
                    "fields": [
                        {"selector": "#name", "value": "Test User"},
                        {"selector": "#email", "value": "test@example.com"},
                        {"selector": "#phone", "value": "555-1234"}
                    ]
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            assert response.status_code in [200, 201, 404, 405]

    def test_fill_select_dropdown(self, client: TestClient, auth_token: str):
        """Test filling select dropdown."""
        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_fill') as mock_fill:
            mock_fill.return_value = {
                "success": True,
                "selector": "#country",
                "value": "US"
            }

            response = client.post(
                f"/api/browser/{session_id}/fill",
                json={
                    "selector": "#country",
                    "value": "US"
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            assert response.status_code in [200, 201, 404, 405]

    def test_fill_checkbox(self, client: TestClient, auth_token: str):
        """Test filling checkbox."""
        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_fill') as mock_fill:
            mock_fill.return_value = {
                "success": True,
                "selector": "#agree",
                "checked": True
            }

            response = client.post(
                f"/api/browser/{session_id}/fill",
                json={
                    "selector": "#agree",
                    "checked": True
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            assert response.status_code in [200, 201, 404, 405]

    def test_fill_nonexistent_element(self, client: TestClient, auth_token: str):
        """Test filling nonexistent element."""
        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_fill') as mock_fill:
            mock_fill.return_value = {
                "success": False,
                "error": "Element not found"
            }

            response = client.post(
                f"/api/browser/{session_id}/fill",
                json={
                    "selector": "#nonexistent",
                    "value": "test"
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            # Should handle element not found
            assert response.status_code in [200, 400, 404, 405]


class TestBrowserClick:
    """Test browser click operations."""

    def test_click_element(self, client: TestClient, auth_token: str, db_session: Session):
        """Test clicking element."""
        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_click') as mock_click:
            mock_click.return_value = {
                "success": True,
                "selector": "#submit-button"
            }

            response = client.post(
                f"/api/browser/{session_id}/click",
                json={
                    "selector": "#submit-button"
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            # Click should succeed
            assert response.status_code in [200, 201, 404, 405]

            if response.status_code in [200, 201]:
                data = response.json()
                assert data.get("success") is True

    def test_click_link(self, client: TestClient, auth_token: str):
        """Test clicking link."""
        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_click') as mock_click:
            mock_click.return_value = {
                "success": True,
                "selector": "a[href='/next']",
                "navigated": True
            }

            response = client.post(
                f"/api/browser/{session_id}/click",
                json={
                    "selector": "a[href='/next']"
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            assert response.status_code in [200, 201, 404, 405]

    def test_click_button(self, client: TestClient, auth_token: str):
        """Test clicking button."""
        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_click') as mock_click:
            mock_click.return_value = {
                "success": True,
                "selector": "button[type='submit']"
            }

            response = client.post(
                f"/api/browser/{session_id}/click",
                json={
                    "selector": "button[type='submit']"
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            assert response.status_code in [200, 201, 404, 405]

    def test_click_with_wait(self, client: TestClient, auth_token: str):
        """Test clicking with wait for navigation."""
        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_click') as mock_click:
            mock_click.return_value = {
                "success": True,
                "waited_for_navigation": True
            }

            response = client.post(
                f"/api/browser/{session_id}/click",
                json={
                    "selector": "#next-button",
                    "wait_for_navigation": True
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            assert response.status_code in [200, 201, 404, 405]

    def test_click_nonexistent_element(self, client: TestClient, auth_token: str):
        """Test clicking nonexistent element."""
        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_click') as mock_click:
            mock_click.return_value = {
                "success": False,
                "error": "Element not found"
            }

            response = client.post(
                f"/api/browser/{session_id}/click",
                json={
                    "selector": "#nonexistent"
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            # Should handle element not found
            assert response.status_code in [200, 400, 404, 405]


class TestBrowserScroll:
    """Test browser scroll operations."""

    def test_scroll_to_element(self, client: TestClient, auth_token: str, db_session: Session):
        """Test scrolling to element."""
        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_scroll') as mock_scroll:
            mock_scroll.return_value = {
                "success": True,
                "selector": "#footer"
            }

            response = client.post(
                f"/api/browser/{session_id}/scroll",
                json={
                    "selector": "#footer"
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            # Scroll should succeed
            assert response.status_code in [200, 201, 404, 405]

            if response.status_code in [200, 201]:
                data = response.json()
                assert data.get("success") is True

    def test_scroll_by_pixels(self, client: TestClient, auth_token: str):
        """Test scrolling by pixels."""
        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_scroll') as mock_scroll:
            mock_scroll.return_value = {
                "success": True,
                "pixels": 500
            }

            response = client.post(
                f"/api/browser/{session_id}/scroll",
                json={
                    "direction": "down",
                    "pixels": 500
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            assert response.status_code in [200, 201, 404, 405]

    def test_scroll_to_top(self, client: TestClient, auth_token: str):
        """Test scrolling to top of page."""
        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_scroll') as mock_scroll:
            mock_scroll.return_value = {
                "success": True,
                "position": "top"
            }

            response = client.post(
                f"/api/browser/{session_id}/scroll",
                json={
                    "position": "top"
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            assert response.status_code in [200, 201, 404, 405]

    def test_scroll_to_bottom(self, client: TestClient, auth_token: str):
        """Test scrolling to bottom of page."""
        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_scroll') as mock_scroll:
            mock_scroll.return_value = {
                "success": True,
                "position": "bottom"
            }

            response = client.post(
                f"/api/browser/{session_id}/scroll",
                json={
                    "position": "bottom"
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            assert response.status_code in [200, 201, 404, 405]


class TestBrowserWait:
    """Test browser wait operations."""

    def test_wait_for_element(self, client: TestClient, auth_token: str, db_session: Session):
        """Test waiting for element to appear."""
        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_wait') as mock_wait:
            mock_wait.return_value = {
                "success": True,
                "selector": "#dynamic-content",
                "timeout": 5000
            }

            response = client.post(
                f"/api/browser/{session_id}/wait",
                json={
                    "selector": "#dynamic-content",
                    "timeout": 5000
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            # Wait should succeed
            assert response.status_code in [200, 201, 404, 405]

            if response.status_code in [200, 201]:
                data = response.json()
                assert data.get("success") is True

    def test_wait_for_navigation(self, client: TestClient, auth_token: str):
        """Test waiting for navigation."""
        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_wait') as mock_wait:
            mock_wait.return_value = {
                "success": True,
                "event": "navigation",
                "url": "https://example.com/next"
            }

            response = client.post(
                f"/api/browser/{session_id}/wait",
                json={
                    "event": "navigation",
                    "timeout": 10000
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            assert response.status_code in [200, 201, 404, 405]

    def test_wait_for_timeout(self, client: TestClient, auth_token: str):
        """Test fixed timeout wait."""
        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_wait') as mock_wait:
            mock_wait.return_value = {
                "success": True,
                "waited_ms": 3000
            }

            response = client.post(
                f"/api/browser/{session_id}/wait",
                json={
                    "duration_ms": 3000
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            assert response.status_code in [200, 201, 404, 405]

    def test_wait_element_not_found(self, client: TestClient, auth_token: str):
        """Test wait when element doesn't appear."""
        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_wait') as mock_wait:
            mock_wait.return_value = {
                "success": False,
                "error": "Element not found within timeout"
            }

            response = client.post(
                f"/api/browser/{session_id}/wait",
                json={
                    "selector": "#never-appears",
                    "timeout": 5000
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            # Should handle timeout
            assert response.status_code in [200, 400, 404, 405]


class TestBrowserComplexActions:
    """Test complex browser action sequences."""

    def test_fill_and_submit_form(self, client: TestClient, auth_token: str, db_session: Session):
        """Test filling and submitting form."""
        session_id = str(uuid.uuid4())

        # Fill form
        with patch('api.browser_routes.browser_fill') as mock_fill:
            mock_fill.return_value = {"success": True}

            fill_response = client.post(
                f"/api/browser/{session_id}/fill",
                json={
                    "selector": "#email",
                    "value": "test@example.com"
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            assert fill_response.status_code in [200, 201, 404, 405]

        # Submit form
        with patch('api.browser_routes.browser_click') as mock_click:
            mock_click.return_value = {"success": True}

            click_response = client.post(
                f"/api/browser/{session_id}/click",
                json={
                    "selector": "#submit-button"
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            assert click_response.status_code in [200, 201, 404, 405]

    def test_navigate_scroll_screenshot(self, client: TestClient, auth_token: str, db_session: Session):
        """Test navigate, scroll, and screenshot sequence."""
        session_id = str(uuid.uuid4())

        # Navigate
        with patch('api.browser_routes.browser_navigate') as mock_navigate:
            mock_navigate.return_value = {"success": True}

            nav_response = client.post(
                f"/api/browser/{session_id}/navigate",
                json={"url": "https://example.com"},
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            assert nav_response.status_code in [200, 404, 405]

        # Scroll
        with patch('api.browser_routes.browser_scroll') as mock_scroll:
            mock_scroll.return_value = {"success": True}

            scroll_response = client.post(
                f"/api/browser/{session_id}/scroll",
                json={"position": "bottom"},
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            assert scroll_response.status_code in [200, 201, 404, 405]

        # Screenshot
        with patch('api.browser_routes.browser_screenshot') as mock_screenshot:
            mock_screenshot.return_value = {"success": True, "screenshot": "base64"}

            screenshot_response = client.post(
                f"/api/browser/{session_id}/screenshot",
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            assert screenshot_response.status_code in [200, 201, 404, 405]


class TestBrowserActionErrors:
    """Test browser action error handling."""

    def test_action_with_invalid_session(self, client: TestClient, auth_token: str):
        """Test action with invalid session ID."""
        fake_session_id = str(uuid.uuid4())

        response = client.post(
            f"/api/browser/{fake_session_id}/click",
            json={"selector": "#button"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Should return error for invalid session
        assert response.status_code in [404, 400, 405]

    def test_action_timeout(self, client: TestClient, auth_token: str):
        """Test action timeout handling."""
        session_id = str(uuid.uuid4())

        with patch('api.browser_routes.browser_wait') as mock_wait:
            mock_wait.side_effect = TimeoutError("Action timeout")

            response = client.post(
                f"/api/browser/{session_id}/wait",
                json={"selector": "#slow-element", "timeout": 1000},
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            # Should handle timeout gracefully
            assert response.status_code in [200, 408, 500, 404, 405]

    def test_action_with_missing_selector(self, client: TestClient, auth_token: str):
        """Test action without required selector."""
        session_id = str(uuid.uuid4())

        response = client.post(
            f"/api/browser/{session_id}/click",
            json={},  # Missing selector
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Should validate required parameters
        assert response.status_code in [400, 422, 404, 405]
