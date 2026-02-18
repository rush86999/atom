"""
Canvas Email Routes API Tests

Tests for email canvas endpoints including:
- Creating an email canvas
- Adding a message
- Saving a draft
- Categorizing an email
- Getting an email canvas
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from main_api_app import app


class TestCanvasEmailRoutes:
    """Test email canvas API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @patch('api.canvas_email_routes.EmailCanvasService')
    def test_create_email_canvas_success(self, mock_service_class, client):
        """Test successful email canvas creation."""
        mock_service = Mock()
        mock_service.create_email_canvas.return_value = {
            "success": True,
            "canvas_id": "canvas-123",
            "subject": "Test Subject"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/email/create",
            json={
                "user_id": "user-123",
                "subject": "Project Update",
                "recipients": ["user1@example.com", "user2@example.com"]
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "canvas_id" in data or "success" in data

    @patch('api.canvas_email_routes.EmailCanvasService')
    def test_create_email_canvas_failure(self, mock_service_class, client):
        """Test email canvas creation with service error."""
        mock_service = Mock()
        mock_service.create_email_canvas.return_value = {
            "success": False,
            "error": "Invalid recipients"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/email/create",
            json={
                "user_id": "user-123",
                "subject": "Test",
                "recipients": ["invalid-email"]
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data or "error" in data or "message" in data

    @patch('api.canvas_email_routes.EmailCanvasService')
    def test_create_email_canvas_with_template(self, mock_service_class, client):
        """Test creating email canvas with template."""
        mock_service = Mock()
        mock_service.create_email_canvas.return_value = {
            "success": True,
            "canvas_id": "canvas-template"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/email/create",
            json={
                "user_id": "user-456",
                "subject": "Newsletter",
                "recipients": ["sub@example.com"],
                "template": "newsletter_template"
            }
        )

        assert response.status_code == 200

    @patch('api.canvas_email_routes.EmailCanvasService')
    def test_create_email_canvas_with_all_params(self, mock_service_class, client):
        """Test creating email canvas with all parameters."""
        mock_service = Mock()
        mock_service.create_email_canvas.return_value = {
            "success": True,
            "canvas_id": "canvas-full"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/email/create",
            json={
                "user_id": "user-789",
                "subject": "Complete Email",
                "recipients": ["to@example.com"],
                "canvas_id": "existing-canvas",
                "agent_id": "agent-123",
                "layout": "conversation",
                "template": "custom"
            }
        )

        assert response.status_code == 200

    @patch('api.canvas_email_routes.EmailCanvasService')
    def test_create_email_canvas_calls_service(self, mock_service_class, client):
        """Test that create calls service correctly."""
        mock_service = Mock()
        mock_service.create_email_canvas.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/email/create",
            json={
                "user_id": "user-call",
                "subject": "Test",
                "recipients": ["test@example.com"]
            }
        )

        assert response.status_code == 200
        mock_service.create_email_canvas.assert_called_once()

    @patch('api.canvas_email_routes.EmailCanvasService')
    def test_add_message_success(self, mock_service_class, client):
        """Test successfully adding a message."""
        mock_service = Mock()
        mock_service.add_message_to_thread.return_value = {
            "success": True,
            "message_id": "msg-123",
            "subject": "Re: Test"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/email/canvas-123/message",
            json={
                "user_id": "user-123",
                "from_email": "sender@example.com",
                "to_emails": ["recipient@example.com"],
                "subject": "Re: Discussion",
                "body": "This is a reply"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "message_id" in data or "success" in data

    @patch('api.canvas_email_routes.EmailCanvasService')
    def test_add_message_failure(self, mock_service_class, client):
        """Test adding message with service error."""
        mock_service = Mock()
        mock_service.add_message_to_thread.return_value = {
            "success": False,
            "error": "Canvas not found"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/email/invalid-canvas/message",
            json={
                "user_id": "user-123",
                "from_email": "from@example.com",
                "to_emails": ["to@example.com"],
                "subject": "Test",
                "body": "Test body"
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data or "error" in data or "message" in data

    @patch('api.canvas_email_routes.EmailCanvasService')
    def test_add_message_with_attachments(self, mock_service_class, client):
        """Test adding message with attachments."""
        mock_service = Mock()
        mock_service.add_message_to_thread.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/email/canvas-123/message",
            json={
                "user_id": "user-456",
                "from_email": "sender@example.com",
                "to_emails": ["recipient@example.com"],
                "subject": "With Attachments",
                "body": "Please find attached",
                "attachments": [
                    {"filename": "doc.pdf", "size": 1024},
                    {"filename": "image.png", "size": 2048}
                ]
            }
        )

        assert response.status_code == 200

    @patch('api.canvas_email_routes.EmailCanvasService')
    def test_add_message_calls_service(self, mock_service_class, client):
        """Test that add_message calls service correctly."""
        mock_service = Mock()
        mock_service.add_message_to_thread.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/email/canvas-test/message",
            json={
                "user_id": "user-test",
                "from_email": "from@test.com",
                "to_emails": ["to@test.com"],
                "subject": "Test Subject",
                "body": "Test Body"
            }
        )

        assert response.status_code == 200
        mock_service.add_message_to_thread.assert_called_once_with(
            canvas_id="canvas-test",
            user_id="user-test",
            from_email="from@test.com",
            to_emails=["to@test.com"],
            subject="Test Subject",
            body="Test Body",
            attachments=None
        )

    @patch('api.canvas_email_routes.EmailCanvasService')
    def test_save_draft_success(self, mock_service_class, client):
        """Test successfully saving a draft."""
        mock_service = Mock()
        mock_service.save_draft.return_value = {
            "success": True,
            "draft_id": "draft-123",
            "subject": "Draft Subject"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/email/canvas-123/draft",
            json={
                "user_id": "user-123",
                "to_emails": ["recipient@example.com"],
                "subject": "Draft Email",
                "body": "Draft content"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "draft_id" in data or "success" in data

    @patch('api.canvas_email_routes.EmailCanvasService')
    def test_save_draft_with_cc(self, mock_service_class, client):
        """Test saving draft with CC recipients."""
        mock_service = Mock()
        mock_service.save_draft.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/email/canvas-123/draft",
            json={
                "user_id": "user-456",
                "to_emails": ["primary@example.com"],
                "cc_emails": ["cc1@example.com", "cc2@example.com"],
                "subject": "With CC",
                "body": "Content"
            }
        )

        assert response.status_code == 200

    @patch('api.canvas_email_routes.EmailCanvasService')
    def test_save_draft_calls_service(self, mock_service_class, client):
        """Test that save_draft calls service correctly."""
        mock_service = Mock()
        mock_service.save_draft.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/email/canvas-test/draft",
            json={
                "user_id": "user-test",
                "to_emails": ["to@test.com"],
                "subject": "Draft Test",
                "body": "Draft body"
            }
        )

        assert response.status_code == 200
        mock_service.save_draft.assert_called_once_with(
            canvas_id="canvas-test",
            user_id="user-test",
            to_emails=["to@test.com"],
            cc_emails=None,
            subject="Draft Test",
            body="Draft body"
        )

    @patch('api.canvas_email_routes.EmailCanvasService')
    def test_categorize_email_success(self, mock_service_class, client):
        """Test successfully categorizing an email."""
        mock_service = Mock()
        mock_service.categorize_email.return_value = {
            "success": True,
            "category": "work",
            "color": "#FF0000"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/email/canvas-123/categorize",
            json={
                "user_id": "user-123",
                "category": "work",
                "color": "#FF0000"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "category" in data or "success" in data

    @patch('api.canvas_email_routes.EmailCanvasService')
    def test_categorize_email_failure(self, mock_service_class, client):
        """Test categorizing with service error."""
        mock_service = Mock()
        mock_service.categorize_email.return_value = {
            "success": False,
            "error": "Canvas not found"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/email/invalid/categorize",
            json={
                "user_id": "user-123",
                "category": "personal"
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data or "error" in data or "message" in data

    @patch('api.canvas_email_routes.EmailCanvasService')
    def test_categorize_email_different_categories(self, mock_service_class, client):
        """Test categorizing with different categories."""
        mock_service = Mock()
        mock_service.categorize_email.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        categories = [
            {"category": "work", "color": "#0000FF"},
            {"category": "personal", "color": "#00FF00"},
            {"category": "urgent", "color": "#FF0000"},
            {"category": "newsletter", "color": None}
        ]

        for cat in categories:
            response = client.post(
                "/api/canvas/email/canvas-123/categorize",
                json={
                    "user_id": "user-789",
                    "category": cat["category"],
                    "color": cat["color"]
                }
            )
            assert response.status_code == 200

    @patch('api.canvas_email_routes.EmailCanvasService')
    def test_categorize_email_calls_service(self, mock_service_class, client):
        """Test that categorize_email calls service correctly."""
        mock_service = Mock()
        mock_service.categorize_email.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/email/canvas-test/categorize",
            json={
                "user_id": "user-test",
                "category": "important",
                "color": "#FFA500"
            }
        )

        assert response.status_code == 200
        mock_service.categorize_email.assert_called_once_with(
            canvas_id="canvas-test",
            user_id="user-test",
            category="important",
            color="#FFA500"
        )

    @patch('api.canvas_email_routes.EmailCanvasService')
    def test_add_multiple_messages(self, mock_service_class, client):
        """Test adding multiple messages to same thread."""
        mock_service = Mock()
        mock_service.add_message_to_thread.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        messages = [
            {"subject": "First", "body": "First message"},
            {"subject": "Re: First", "body": "Second message"},
            {"subject": "Re: First", "body": "Third message"}
        ]

        for msg in messages:
            response = client.post(
                "/api/canvas/email/canvas-thread/message",
                json={
                    "user_id": "user-multi",
                    "from_email": "sender@example.com",
                    "to_emails": ["recipient@example.com"],
                    "subject": msg["subject"],
                    "body": msg["body"]
                }
            )
            assert response.status_code == 200

    @patch('api.canvas_email_routes.EmailCanvasService')
    def test_save_multiple_drafts(self, mock_service_class, client):
        """Test saving multiple drafts."""
        mock_service = Mock()
        mock_service.save_draft.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        drafts = [
            {"subject": "Draft 1", "to_emails": ["user1@example.com"]},
            {"subject": "Draft 2", "to_emails": ["user2@example.com"]},
            {"subject": "Draft 3", "to_emails": ["user3@example.com"]}
        ]

        for draft in drafts:
            response = client.post(
                "/api/canvas/email/canvas-drafts/draft",
                json={
                    "user_id": "user-drafts",
                    "to_emails": draft["to_emails"],
                    "subject": draft["subject"],
                    "body": f"Content for {draft['subject']}"
                }
            )
            assert response.status_code == 200

    @patch('api.canvas_email_routes.EmailCanvasService')
    def test_email_endpoints_return_json(self, mock_service_class, client):
        """Test that email endpoints return JSON."""
        mock_service = Mock()
        mock_service.create_email_canvas.return_value = {"success": True}
        mock_service.add_message_to_thread.return_value = {"success": True}
        mock_service.save_draft.return_value = {"success": True}
        mock_service.categorize_email.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        # Test create endpoint
        response = client.post(
            "/api/canvas/email/create",
            json={"user_id": "u", "subject": "s", "recipients": ["t@example.com"]}
        )
        assert response.headers["content-type"].startswith("application/json")

        # Test add message endpoint
        response = client.post(
            "/api/canvas/email/c/message",
            json={
                "user_id": "u",
                "from_email": "f@example.com",
                "to_emails": ["t@example.com"],
                "subject": "s",
                "body": "b"
            }
        )
        assert response.headers["content-type"].startswith("application/json")

        # Test save draft endpoint
        response = client.post(
            "/api/canvas/email/c/draft",
            json={"user_id": "u", "to_emails": ["t@example.com"]}
        )
        assert response.headers["content-type"].startswith("application/json")

        # Test categorize endpoint
        response = client.post(
            "/api/canvas/email/c/categorize",
            json={"user_id": "u", "category": "work"}
        )
        assert response.headers["content-type"].startswith("application/json")
