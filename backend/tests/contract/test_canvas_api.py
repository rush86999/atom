"""Contract tests for canvas API endpoints using Schemathesis schema validation."""
import pytest
from fastapi.testclient import TestClient
from main_api_app import app
from tests.contract.conftest import schema


class TestCanvasEndpoints:
    """Contract tests for canvas presentation endpoints."""

    def test_canvas_submit_contracts(self):
        """Test POST /api/canvas/submit conforms to OpenAPI spec."""
        operation = schema["/api/canvas/submit"]["POST"]
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
            operation.validate_response(response)
            # Schemathesis validates schema
            assert response.status_code in [200, 400, 401, 422]

    def test_canvas_status_contracts(self):
        """Test GET /api/canvas/status conforms to OpenAPI spec."""
        operation = schema["/api/canvas/status"]["GET"]
        with TestClient(app) as client:
            response = client.get("/api/canvas/status")
            operation.validate_response(response)
            # Schemathesis validates schema
            assert response.status_code in [200, 401, 404, 422]

    def test_canvas_state_contracts(self):
        """Test GET /api/canvas/state/{canvas_id} conforms to OpenAPI spec."""
        operation = schema["/api/canvas/state/{canvas_id}"]["GET"]
        with TestClient(app) as client:
            response = client.get("/api/canvas/state/test-canvas-id")
            operation.validate_response(response)
            # Schemathesis validates schema
            assert response.status_code in [200, 401, 404, 422]


class TestCanvasTypeEndpoints:
    """Contract tests for specialized canvas type endpoints."""

    def test_canvas_docs_contracts(self):
        """Test POST /api/canvas/docs/create conforms to OpenAPI spec."""
        operation = schema["/api/canvas/docs/create"]["POST"]
        with TestClient(app) as client:
            response = client.post(
                "/api/canvas/docs/create",
                json={
                    "canvas_id": "test-docs-canvas",
                    "title": "Test Document",
                    "content": "Test content"
                }
            )
            operation.validate_response(response)
            assert response.status_code in [200, 400, 401, 422]

    def test_canvas_sheets_contracts(self):
        """Test POST /api/canvas/sheets/create conforms to OpenAPI spec."""
        operation = schema["/api/canvas/sheets/create"]["POST"]
        with TestClient(app) as client:
            response = client.post(
                "/api/canvas/sheets/create",
                json={
                    "canvas_id": "test-sheets-canvas",
                    "title": "Test Spreadsheet"
                }
            )
            operation.validate_response(response)
            assert response.status_code in [200, 400, 401, 422]

    def test_canvas_email_contracts(self):
        """Test POST /api/canvas/email/create conforms to OpenAPI spec."""
        operation = schema["/api/canvas/email/create"]["POST"]
        with TestClient(app) as client:
            response = client.post(
                "/api/canvas/email/create",
                json={
                    "canvas_id": "test-email-canvas",
                    "to": "test@example.com",
                    "subject": "Test Email"
                }
            )
            operation.validate_response(response)
            assert response.status_code in [200, 400, 401, 422]

    def test_canvas_orchestration_contracts(self):
        """Test POST /api/canvas/orchestration/create conforms to OpenAPI spec."""
        operation = schema["/api/canvas/orchestration/create"]["POST"]
        with TestClient(app) as client:
            response = client.post(
                "/api/canvas/orchestration/create",
                json={
                    "canvas_id": "test-orchestration-canvas",
                    "title": "Test Orchestration"
                }
            )
            operation.validate_response(response)
            assert response.status_code in [200, 400, 401, 422]

    def test_canvas_terminal_contracts(self):
        """Test POST /api/canvas/terminal/create conforms to OpenAPI spec."""
        operation = schema["/api/canvas/terminal/create"]["POST"]
        with TestClient(app) as client:
            response = client.post(
                "/api/canvas/terminal/create",
                json={
                    "canvas_id": "test-terminal-canvas",
                    "title": "Test Terminal"
                }
            )
            operation.validate_response(response)
            assert response.status_code in [200, 400, 401, 422]

    def test_canvas_coding_contracts(self):
        """Test POST /api/canvas/coding/create conforms to OpenAPI spec."""
        operation = schema["/api/canvas/coding/create"]["POST"]
        with TestClient(app) as client:
            response = client.post(
                "/api/canvas/coding/create",
                json={
                    "canvas_id": "test-coding-canvas",
                    "title": "Test Coding Canvas"
                }
            )
            operation.validate_response(response)
            assert response.status_code in [200, 400, 401, 422]

    def test_canvas_types_contracts(self):
        """Test GET /api/canvas/types conforms to OpenAPI spec."""
        operation = schema["/api/canvas/types"]["GET"]
        with TestClient(app) as client:
            response = client.get("/api/canvas/types")
            operation.validate_response(response)
            assert response.status_code in [200, 401, 422]
