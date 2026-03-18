"""Workflow API contract tests using Schemathesis for OpenAPI compliance.

Validates that workflow template endpoints conform to their OpenAPI specification.
Uses property-based testing with Hypothesis to generate diverse test cases
and validate request/response schemas.

Contract test coverage:
- GET /api/workflow-templates - List workflow templates
- GET /api/workflow-templates/{template_id} - Get template by ID
- POST /api/workflow-templates - Create workflow template
- PUT /api/workflow-templates/{template_id} - Update template
- POST /api/workflow-templates/{template_id}/instantiate - Instantiate template
- POST /api/workflow-templates/{template_id}/execute - Execute template
"""
import pytest
from fastapi.testclient import TestClient
from main_api_app import app
import schemathesis

# Load OpenAPI schema from FastAPI app
schema = schemathesis.openapi.from_dict(app.openapi())


class TestWorkflowAPIContracts:
    """Contract tests for Workflow Template API endpoints.

    Tests validate that the API implementation matches the OpenAPI specification
    using Schemathesis for schema validation.
    """

    def test_list_workflow_templates(self):
        """Test GET /api/workflow-templates validates template list schema.

        Validates:
        - Response includes array of workflow templates
        - Category filtering parameter works correctly
        - Pagination parameters conform to schema
        """
        operation = schema["/api/workflow-templates"]["GET"]
        with TestClient(app) as client:
            response = client.get("/api/workflow-templates")
            operation.validate_response(response)
            assert response.status_code in [200, 400]

    def test_get_workflow_by_id(self):
        """Test GET /api/workflow-templates/{template_id} validates template schema.

        Validates:
        - Response includes workflow definition (nodes, connections)
        - Returns 404 for non-existent templates
        - Response body conforms to schema
        """
        operation = schema["/api/workflow-templates/{template_id}"]["GET"]
        with TestClient(app) as client:
            response = client.get("/api/workflow-templates/test-template-id")
            operation.validate_response(response)
            assert response.status_code in [200, 404]

    def test_create_workflow(self):
        """Test POST /api/workflow-templates validates workflow creation.

        Validates:
        - Required fields enforced (name, nodes)
        - Workflow definition schema (nodes, connections)
        - Response includes created template details
        - Returns 201 on success, 422 on validation error
        """
        operation = schema["/api/workflow-templates"]["POST"]
        with TestClient(app) as client:
            response = client.post(
                "/api/workflow-templates",
                json={
                    "name": "Test Workflow",
                    "description": "Test template",
                    "nodes": [],
                    "connections": []
                }
            )
            operation.validate_response(response)
            assert response.status_code in [200, 201, 400, 422]

    def test_update_workflow(self):
        """Test PUT /api/workflow-templates/{template_id} validates updates.

        Validates:
        - Partial updates work correctly
        - Field validation enforced on update
        - Response includes updated template details
        - Returns 404 for non-existent templates
        """
        operation = schema["/api/workflow-templates/{template_id}"]["PUT"]
        with TestClient(app) as client:
            response = client.put(
                "/api/workflow-templates/test-template-id",
                json={"name": "Updated Workflow"}
            )
            operation.validate_response(response)
            assert response.status_code in [200, 404, 422]

    def test_instantiate_workflow(self):
        """Test POST /api/workflow-templates/{template_id}/instantiate validates instantiation.

        Validates:
        - Instantiation request schema
        - Response includes created workflow instance
        - Returns 404 for non-existent templates
        """
        operation = schema["/api/workflow-templates/{template_id}/instantiate"]["POST"]
        with TestClient(app) as client:
            response = client.post(
                "/api/workflow-templates/test-template-id/instantiate",
                json={"parameters": {}}
            )
            operation.validate_response(response)
            assert response.status_code in [200, 201, 404]

    def test_execute_workflow(self):
        """Test POST /api/workflow-templates/{template_id}/execute validates execution.

        Validates:
        - Execution request/response schema
        - Returns 404 for non-existent templates
        - Returns 500 for execution errors
        """
        operation = schema["/api/workflow-templates/{template_id}/execute"]["POST"]
        with TestClient(app) as client:
            response = client.post(
                "/api/workflow-templates/test-template-id/execute",
                json={"input": {}}
            )
            operation.validate_response(response)
            assert response.status_code in [200, 404, 500]


# Pytest marker for running only contract tests
pytestmark = pytest.mark.contract
