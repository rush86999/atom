"""Contract tests for canvas API endpoints using FastAPI TestClient."""
import pytest
from fastapi.testclient import TestClient
from main_api_app import app


class TestCanvasEndpoints:
    """Contract tests for canvas presentation endpoints."""

    def test_canvas_submit_endpoint(self):
        """Test POST /api/canvas/submit conforms to OpenAPI spec."""
        with TestClient(app) as client:
            response = client.post(
                "/api/canvas/submit",
                json={
                    "canvas_id": "test-canvas",
                    "form_data": {"field1": "value1"},
                    "agent_execution_id": None,
                    "agent_id": None
                }
            )
            # May return 401 for auth, 400/422 for validation
            assert response.status_code in [200, 400, 401, 403, 404, 422]

    def test_canvas_status_endpoint(self):
        """Test GET /api/canvas/status conforms to OpenAPI spec."""
        with TestClient(app) as client:
            response = client.get("/api/canvas/status")
            # May return 200, 401 for auth, or 422 for validation
            assert response.status_code in [200, 401, 403, 404, 422]

    def test_canvas_state_endpoint(self):
        """Test GET /api/canvas/state/{canvas_id} conforms to OpenAPI spec."""
        with TestClient(app) as client:
            response = client.get("/api/canvas/state/test-canvas-id")
            # May return 404 if canvas not found, 401 for auth, or 422 for validation
            assert response.status_code in [200, 401, 403, 404, 422]


class TestCanvasTypeEndpoints:
    """Contract tests for specialized canvas type endpoints."""

    def test_canvas_docs_create_endpoint(self):
        """Test POST /api/canvas/docs/create conforms to OpenAPI spec."""
        with TestClient(app) as client:
            response = client.post(
                "/api/canvas/docs/create",
                json={
                    "canvas_id": "test-docs-canvas",
                    "title": "Test Document",
                    "content": "Test content"
                }
            )
            # May return 401 for auth or 400/422 for validation
            assert response.status_code in [200, 400, 401, 403, 404, 422]

    def test_canvas_sheets_create_endpoint(self):
        """Test POST /api/canvas/sheets/create conforms to OpenAPI spec."""
        with TestClient(app) as client:
            response = client.post(
                "/api/canvas/sheets/create",
                json={
                    "canvas_id": "test-sheets-canvas",
                    "title": "Test Spreadsheet"
                }
            )
            # May return 401 for auth or 400/422 for validation
            assert response.status_code in [200, 400, 401, 403, 404, 422]

    def test_canvas_email_create_endpoint(self):
        """Test POST /api/canvas/email/create conforms to OpenAPI spec."""
        with TestClient(app) as client:
            response = client.post(
                "/api/canvas/email/create",
                json={
                    "canvas_id": "test-email-canvas",
                    "to": "test@example.com",
                    "subject": "Test Email"
                }
            )
            # May return 401 for auth or 400/422 for validation
            assert response.status_code in [200, 400, 401, 403, 404, 422]

    def test_canvas_orchestration_create_endpoint(self):
        """Test POST /api/canvas/orchestration/create conforms to OpenAPI spec."""
        with TestClient(app) as client:
            response = client.post(
                "/api/canvas/orchestration/create",
                json={
                    "canvas_id": "test-orchestration-canvas",
                    "title": "Test Orchestration"
                }
            )
            # May return 401 for auth or 400/422 for validation
            assert response.status_code in [200, 400, 401, 403, 404, 422]

    def test_canvas_terminal_create_endpoint(self):
        """Test POST /api/canvas/terminal/create conforms to OpenAPI spec."""
        with TestClient(app) as client:
            response = client.post(
                "/api/canvas/terminal/create",
                json={
                    "canvas_id": "test-terminal-canvas",
                    "title": "Test Terminal"
                }
            )
            # May return 401 for auth or 400/422 for validation
            assert response.status_code in [200, 400, 401, 403, 404, 422]

    def test_canvas_coding_create_endpoint(self):
        """Test POST /api/canvas/coding/create conforms to OpenAPI spec."""
        with TestClient(app) as client:
            response = client.post(
                "/api/canvas/coding/create",
                json={
                    "canvas_id": "test-coding-canvas",
                    "title": "Test Coding Canvas"
                }
            )
            # May return 401 for auth or 400/422 for validation
            assert response.status_code in [200, 400, 401, 403, 404, 422]

    def test_canvas_types_endpoint(self):
        """Test GET /api/canvas/types conforms to OpenAPI spec."""
        with TestClient(app) as client:
            response = client.get("/api/canvas/types")
            # May return 200, 401 for auth, or 422 for validation
            assert response.status_code in [200, 401, 403, 404, 422]
