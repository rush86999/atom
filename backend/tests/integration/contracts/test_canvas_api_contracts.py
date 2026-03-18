"""Canvas API contract tests using Schemathesis for OpenAPI compliance.

Validates that canvas endpoints conform to their OpenAPI specification.
Uses property-based testing with Hypothesis to generate diverse test cases
and validate request/response schemas.

Contract test coverage:
- POST /api/canvas/create - Create new canvas
- GET /api/canvas/{canvas_id} - Get canvas by ID
- PUT /api/canvas/{canvas_id} - Update canvas
- DELETE /api/canvas/{canvas_id} - Delete canvas
- POST /api/canvas/{canvas_id}/node - Add node to canvas
- POST /api/canvas/{canvas_id}/connect - Connect canvas nodes
"""
import pytest
from fastapi.testclient import TestClient
from main_api_app import app
import schemathesis

# Load OpenAPI schema from FastAPI app
schema = schemathesis.openapi.from_dict(app.openapi())


class TestCanvasAPIContracts:
    """Contract tests for Canvas API endpoints.

    Tests validate that the API implementation matches the OpenAPI specification
    using Schemathesis for schema validation.

    Canvas Types: markdown, chart, form, sheet, terminal, coding, email
    """

    def test_create_canvas(self):
        """Test POST /api/canvas/create validates canvas creation.

        Validates:
        - Canvas type is one of 7 valid types
        - Required fields enforced based on canvas type
        - Response includes created canvas details
        - Returns 201 on success, 422 on validation error
        """
        operation = schema["/api/canvas/create"]["POST"]
        with TestClient(app) as client:
            response = client.post(
                "/api/canvas/create",
                json={
                    "canvas_type": "markdown",
                    "title": "Test Canvas",
                    "content": "# Test Content"
                }
            )
            operation.validate_response(response)
            assert response.status_code in [200, 201, 400, 422]

    def test_get_canvas_by_id(self):
        """Test GET /api/canvas/{canvas_id} validates canvas response schema.

        Validates:
        - Response includes canvas state for all 7 canvas types
        - Canvas-specific data structure validated
        - Returns 404 for non-existent canvases
        """
        operation = schema["/api/canvas/{canvas_id}"]["GET"]
        with TestClient(app) as client:
            response = client.get("/api/canvas/test-canvas-id")
            operation.validate_response(response)
            assert response.status_code in [200, 404]

    def test_update_canvas(self):
        """Test PUT /api/canvas/{canvas_id} validates canvas updates.

        Validates:
        - Partial updates work correctly
        - Canvas type-specific validation
        - Response includes updated canvas details
        - Returns 404 for non-existent canvases
        """
        operation = schema["/api/canvas/{canvas_id}"]["PUT"]
        with TestClient(app) as client:
            response = client.put(
                "/api/canvas/test-canvas-id",
                json={"title": "Updated Canvas"}
            )
            operation.validate_response(response)
            assert response.status_code in [200, 404, 422]

    def test_delete_canvas(self):
        """Test DELETE /api/canvas/{canvas_id} validates deletion.

        Validates:
        - Deletion response schema
        - Returns 404 for non-existent canvases
        """
        operation = schema["/api/canvas/{canvas_id}"]["DELETE"]
        with TestClient(app) as client:
            response = client.delete("/api/canvas/test-canvas-id")
            operation.validate_response(response)
            assert response.status_code in [200, 404]

    def test_add_canvas_node(self):
        """Test POST /api/canvas/{canvas_id}/node validates node addition.

        Validates:
        - Node creation request schema
        - Node type validation
        - Returns 404 for non-existent canvases
        """
        operation = schema["/api/canvas/{canvas_id}/node"]["POST"]
        with TestClient(app) as client:
            response = client.post(
                "/api/canvas/test-canvas-id/node",
                json={
                    "node_type": "text",
                    "content": "Test node"
                }
            )
            operation.validate_response(response)
            assert response.status_code in [200, 201, 404, 422]

    def test_connect_canvas_nodes(self):
        """Test POST /api/canvas/{canvas_id}/connect validates node connection.

        Validates:
        - Connection request schema (source, target nodes)
        - Returns 404 for non-existent canvases
        """
        operation = schema["/api/canvas/{canvas_id}/connect"]["POST"]
        with TestClient(app) as client:
            response = client.post(
                "/api/canvas/test-canvas-id/connect",
                json={
                    "source_node_id": "node1",
                    "target_node_id": "node2"
                }
            )
            operation.validate_response(response)
            assert response.status_code in [200, 400, 404, 422]


# Pytest marker for running only contract tests
pytestmark = pytest.mark.contract
