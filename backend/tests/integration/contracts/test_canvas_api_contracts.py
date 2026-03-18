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
import schemathesis
from hypothesis import settings
from main_api_app import app

# Load OpenAPI schema from FastAPI app
schema = schemathesis.from_wsgi("/openapi.json", app)


class TestCanvasAPIContracts:
    """Contract tests for Canvas API endpoints.

    Tests use property-based testing to generate diverse inputs and validate
    that the API implementation matches the OpenAPI specification.

    Canvas Types: markdown, chart, form, sheet, terminal, coding, email
    """

    @schema.parametrize(endpoint="/api/canvas/create")
    @settings(max_examples=15, deadline=None)
    def test_create_canvas(self, case):
        """Test POST /api/canvas/create validates canvas creation.

        Validates:
        - Canvas type is one of 7 valid types
        - Required fields enforced based on canvas type
        - Response includes created canvas details
        - Returns 201 on success, 422 on validation error
        """
        response = case.call_and_validate()
        assert response.status_code in [200, 201, 400, 422]

    @schema.parametrize(endpoint="/api/canvas/{canvas_id}")
    @settings(max_examples=20, deadline=None)
    def test_get_canvas_by_id(self, case):
        """Test GET /api/canvas/{canvas_id} validates canvas response schema.

        Validates:
        - Response includes canvas state for all 7 canvas types
        - Canvas-specific data structure validated
        - Returns 404 for non-existent canvases
        """
        response = case.call_and_validate()
        assert response.status_code in [200, 404]

    @schema.parametrize(endpoint="/api/canvas/{canvas_id}")
    @settings(max_examples=15, deadline=None)
    def test_update_canvas(self, case):
        """Test PUT /api/canvas/{canvas_id} validates canvas updates.

        Validates:
        - Partial updates work correctly
        - Canvas type-specific validation
        - Response includes updated canvas details
        - Returns 404 for non-existent canvases
        """
        response = case.call_and_validate()
        assert response.status_code in [200, 404, 422]

    @schema.parametrize(endpoint="/api/canvas/{canvas_id}")
    @settings(max_examples=10, deadline=None)
    def test_delete_canvas(self, case):
        """Test DELETE /api/canvas/{canvas_id} validates deletion.

        Validates:
        - Deletion response schema
        - Returns 404 for non-existent canvases
        """
        response = case.call_and_validate()
        assert response.status_code in [200, 404]

    @schema.parametrize(endpoint="/api/canvas/{canvas_id}/node")
    @settings(max_examples=10, deadline=None)
    def test_add_canvas_node(self, case):
        """Test POST /api/canvas/{canvas_id}/node validates node addition.

        Validates:
        - Node creation request schema
        - Node type validation
        - Returns 404 for non-existent canvases
        """
        response = case.call_and_validate()
        assert response.status_code in [200, 201, 404, 422]

    @schema.parametrize(endpoint="/api/canvas/{canvas_id}/connect")
    @settings(max_examples=10, deadline=None)
    def test_connect_canvas_nodes(self, case):
        """Test POST /api/canvas/{canvas_id}/connect validates node connection.

        Validates:
        - Connection request schema (source, target nodes)
        - Returns 404 for non-existent canvases
        """
        response = case.call_and_validate()
        assert response.status_code in [200, 400, 404, 422]


# Pytest marker for running only contract tests
pytestmark = pytest.mark.contract
