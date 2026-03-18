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
import schemathesis
from hypothesis import settings
from main_api_app import app

# Load OpenAPI schema from FastAPI app
schema = schemathesis.from_wsgi("/openapi.json", app)


class TestWorkflowAPIContracts:
    """Contract tests for Workflow Template API endpoints.

    Tests use property-based testing to generate diverse inputs and validate
    that the API implementation matches the OpenAPI specification.
    """

    @schema.parametrize(endpoint="/api/workflow-templates")
    @settings(max_examples=15, deadline=None)
    def test_list_workflow_templates(self, case):
        """Test GET /api/workflow-templates validates template list schema.

        Validates:
        - Response includes array of workflow templates
        - Category filtering parameter works correctly
        - Pagination parameters conform to schema
        """
        response = case.call_and_validate()
        assert response.status_code in [200, 400]

    @schema.parametrize(endpoint="/api/workflow-templates/{template_id}")
    @settings(max_examples=20, deadline=None)
    def test_get_workflow_by_id(self, case):
        """Test GET /api/workflow-templates/{template_id} validates template schema.

        Validates:
        - Response includes workflow definition (nodes, connections)
        - Returns 404 for non-existent templates
        - Response body conforms to schema
        """
        response = case.call_and_validate()
        assert response.status_code in [200, 404]

    @schema.parametrize(endpoint="/api/workflow-templates")
    @settings(max_examples=15, deadline=None)
    def test_create_workflow(self, case):
        """Test POST /api/workflow-templates validates workflow creation.

        Validates:
        - Required fields enforced (name, nodes)
        - Workflow definition schema (nodes, connections)
        - Response includes created template details
        - Returns 201 on success, 422 on validation error
        """
        response = case.call_and_validate()
        assert response.status_code in [200, 201, 400, 422]

    @schema.parametrize(endpoint="/api/workflow-templates/{template_id}")
    @settings(max_examples=10, deadline=None)
    def test_update_workflow(self, case):
        """Test PUT /api/workflow-templates/{template_id} validates updates.

        Validates:
        - Partial updates work correctly
        - Field validation enforced on update
        - Response includes updated template details
        - Returns 404 for non-existent templates
        """
        response = case.call_and_validate()
        assert response.status_code in [200, 404, 422]

    @schema.parametrize(endpoint="/api/workflow-templates/{template_id}/instantiate")
    @settings(max_examples=10, deadline=None)
    def test_instantiate_workflow(self, case):
        """Test POST /api/workflow-templates/{template_id}/instantiate validates instantiation.

        Validates:
        - Instantiation request schema
        - Response includes created workflow instance
        - Returns 404 for non-existent templates
        """
        response = case.call_and_validate()
        assert response.status_code in [200, 201, 404]

    @schema.parametrize(endpoint="/api/workflow-templates/{template_id}/execute")
    @settings(max_examples=10, deadline=None)
    def test_execute_workflow(self, case):
        """Test POST /api/workflow-templates/{template_id}/execute validates execution.

        Validates:
        - Execution request/response schema
        - Returns 404 for non-existent templates
        - Returns 500 for execution errors
        """
        response = case.call_and_validate()
        assert response.status_code in [200, 404, 500]


# Pytest marker for running only contract tests
pytestmark = pytest.mark.contract
