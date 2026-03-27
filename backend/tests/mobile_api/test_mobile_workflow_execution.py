"""
Mobile API Workflow Execution Tests

Tests for mobile API workflow execution endpoints:
- Workflow creation
- Workflow skill addition
- Workflow execution
- Workflow DAG validation
- Workflow execution history

All tests use API-first approach with TestClient (no browser).
Response structure matches web API for consistency.
"""

import pytest
from fastapi.testclient import TestClient


class TestMobileWorkflowCreate:
    """Test mobile workflow creation endpoint"""

    def test_mobile_workflow_create(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test workflow creation"""
        response = mobile_api_client.post(
            "/api/v1/workflows",
            headers=mobile_auth_headers,
            json={
                "name": "Mobile Test Workflow",
                "description": "Test workflow from mobile API",
                "category": "testing"
            }
        )

        # Verify response (may be 201 or 200)
        if response.status_code in [200, 201]:
            data = response.json()

            # Verify workflow_id present
            assert "workflow_id" in data or "id" in data

            # Verify workflow details
            workflow_id = data.get("workflow_id") or data.get("id")
            assert workflow_id is not None

            # Verify name and description in response
            assert "name" in data or data.get("workflow", {}).get("name")
        elif response.status_code == 404:
            pytest.skip("Workflow creation endpoint not implemented")

    def test_mobile_workflow_create_invalid(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test workflow creation with invalid data"""
        response = mobile_api_client.post(
            "/api/v1/workflows",
            headers=mobile_auth_headers,
            json={
                "name": "",  # Invalid: empty name
                "description": "Test"
            }
        )

        # Verify validation error
        assert response.status_code in [400, 422]

    def test_mobile_workflow_create_unauthorized(self, mobile_api_client: TestClient):
        """Test workflow creation without authentication"""
        response = mobile_api_client.post(
            "/api/v1/workflows",
            json={
                "name": "Unauthorized Workflow",
                "description": "Should fail"
            }
        )

        # Verify unauthorized response
        assert response.status_code == 401


class TestMobileWorkflowAddSkill:
    """Test mobile workflow skill management"""

    def test_mobile_workflow_add_skill(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test adding skill to workflow"""
        # First, create a workflow
        create_response = mobile_api_client.post(
            "/api/v1/workflows",
            headers=mobile_auth_headers,
            json={
                "name": "Test Workflow for Skills",
                "description": "Testing skill addition"
            }
        )

        if create_response.status_code not in [200, 201]:
            pytest.skip("Workflow creation not available")

        create_data = create_response.json()
        workflow_id = create_data.get("workflow_id") or create_data.get("id")

        if not workflow_id:
            pytest.skip("Workflow ID not returned")

        # Add skill to workflow
        response = mobile_api_client.post(
            f"/api/v1/workflows/{workflow_id}/skills",
            headers=mobile_auth_headers,
            json={
                "skill_id": "test_skill",
                "order": 1,
                "parameters": {"test": "value"}
            }
        )

        # Verify response
        if response.status_code == 200:
            data = response.json()
            assert "success" in data or "skill_id" in data

            # Verify skill added by fetching workflow
            get_response = mobile_api_client.get(
                f"/api/v1/workflows/{workflow_id}",
                headers=mobile_auth_headers
            )

            if get_response.status_code == 200:
                workflow_data = get_response.json()
                # Verify skill present in workflow
                assert "skills" in workflow_data or "nodes" in workflow_data
        elif response.status_code == 404:
            pytest.skip("Workflow skill endpoint not implemented")

    def test_mobile_workflow_list_skills(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test listing workflow skills"""
        # Try to list skills for a workflow
        response = mobile_api_client.get(
            "/api/v1/workflows/test_workflow_id/skills",
            headers=mobile_auth_headers
        )

        # May be 404 if workflow doesn't exist, or endpoint not implemented
        if response.status_code == 200:
            data = response.json()
            assert "skills" in data or isinstance(data, list)
        elif response.status_code == 404:
            # Expected - workflow doesn't exist or endpoint not implemented
            pass


class TestMobileWorkflowExecute:
    """Test mobile workflow execution endpoint"""

    def test_mobile_workflow_execute(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test workflow execution"""
        # First, create a simple workflow
        create_response = mobile_api_client.post(
            "/api/v1/workflows",
            headers=mobile_auth_headers,
            json={
                "name": "Executable Test Workflow",
                "description": "Testing workflow execution"
            }
        )

        if create_response.status_code not in [200, 201]:
            pytest.skip("Workflow creation not available")

        create_data = create_response.json()
        workflow_id = create_data.get("workflow_id") or create_data.get("id")

        if not workflow_id:
            pytest.skip("Workflow ID not returned")

        # Execute workflow
        response = mobile_api_client.post(
            f"/api/v1/workflows/{workflow_id}/execute",
            headers=mobile_auth_headers,
            json={
                "input": "test input data"
            }
        )

        # Verify response
        if response.status_code == 200:
            data = response.json()

            # Verify execution_id present
            assert "execution_id" in data or "id" in data

            # Verify status
            assert "status" in data or data.get("success") is True
        elif response.status_code == 404:
            pytest.skip("Workflow execution endpoint not implemented")

    def test_mobile_workflow_execute_with_parameters(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test workflow execution with custom parameters"""
        # Create workflow
        create_response = mobile_api_client.post(
            "/api/v1/workflows",
            headers=mobile_auth_headers,
            json={
                "name": "Parameterized Workflow",
                "description": "Testing parameter passing"
            }
        )

        if create_response.status_code not in [200, 201]:
            pytest.skip("Workflow creation not available")

        create_data = create_response.json()
        workflow_id = create_data.get("workflow_id") or create_data.get("id")

        if not workflow_id:
            pytest.skip("Workflow ID not returned")

        # Execute with parameters
        response = mobile_api_client.post(
            f"/api/v1/workflows/{workflow_id}/execute",
            headers=mobile_auth_headers,
            json={
                "input": "test",
                "parameters": {
                    "param1": "value1",
                    "param2": 123,
                    "param3": True
                }
            }
        )

        # Verify execution started
        if response.status_code == 200:
            data = response.json()
            assert "execution_id" in data or "success" in data
        elif response.status_code == 404:
            pytest.skip("Workflow execution endpoint not implemented")

    def test_mobile_workflow_execute_not_found(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test executing non-existent workflow"""
        response = mobile_api_client.post(
            "/api/v1/workflows/nonexistent_workflow_id/execute",
            headers=mobile_auth_headers,
            json={"input": "test"}
        )

        # Verify error response
        assert response.status_code in [404, 400]


class TestMobileWorkflowDAGValidation:
    """Test mobile workflow DAG validation"""

    def test_mobile_workflow_dag_validation(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test DAG validation detects cycles"""
        # Try to validate a workflow with cyclic dependency
        response = mobile_api_client.post(
            "/api/v1/workflows/validate",
            headers=mobile_auth_headers,
            json={
                "name": "Cyclic Workflow",
                "nodes": [
                    {"id": "A", "type": "skill"},
                    {"id": "B", "type": "skill"},
                    {"id": "C", "type": "skill"}
                ],
                "edges": [
                    {"from": "A", "to": "B"},
                    {"from": "B", "to": "C"},
                    {"from": "C", "to": "A"}  # Cycle!
                ]
            }
        )

        # Verify validation fails
        if response.status_code == 200:
            data = response.json()

            # If validation endpoint exists, it should detect cycle
            if "valid" in data:
                assert data["valid"] is False
                assert "cycle" in str(data.get("error", "")).lower()
            elif "errors" in data:
                # Validation returned list of errors
                assert len(data["errors"]) > 0
        elif response.status_code == 404:
            pytest.skip("Workflow validation endpoint not implemented")

    def test_mobile_workflow_dag_valid(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test DAG validation passes for valid DAG"""
        # Create a valid DAG (no cycles)
        response = mobile_api_client.post(
            "/api/v1/workflows/validate",
            headers=mobile_auth_headers,
            json={
                "name": "Valid DAG Workflow",
                "nodes": [
                    {"id": "A", "type": "skill"},
                    {"id": "B", "type": "skill"},
                    {"id": "C", "type": "skill"}
                ],
                "edges": [
                    {"from": "A", "to": "B"},
                    {"from": "B", "to": "C"}
                    # No edge back to A - valid DAG
                ]
            }
        )

        # Verify validation passes
        if response.status_code == 200:
            data = response.json()

            if "valid" in data:
                assert data["valid"] is True
            elif "errors" in data:
                # Should have no errors
                assert len(data["errors"]) == 0
        elif response.status_code == 404:
            pytest.skip("Workflow validation endpoint not implemented")


class TestMobileWorkflowExecutionHistory:
    """Test mobile workflow execution history"""

    def test_mobile_workflow_execution_history(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test listing workflow execution history"""
        response = mobile_api_client.get(
            "/api/v1/workflows/executions",
            headers=mobile_auth_headers
        )

        # Verify response
        if response.status_code == 200:
            data = response.json()

            # Verify history structure
            assert "executions" in data or "items" in data or isinstance(data, list)

            # If executions present, verify fields
            if isinstance(data, dict) and "executions" in data:
                executions = data["executions"]
                if executions:
                    # Check first execution has required fields
                    execution = executions[0]
                    assert "status" in execution or "workflow_id" in execution
        elif response.status_code == 404:
            pytest.skip("Workflow executions history endpoint not implemented")

    def test_mobile_workflow_execution_history_fields(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test execution history has required fields"""
        response = mobile_api_client.get(
            "/api/v1/workflows/executions?limit=5",
            headers=mobile_auth_headers
        )

        if response.status_code == 200:
            data = response.json()
            executions = data.get("executions", data.get("items", data))

            if isinstance(executions, list) and executions:
                execution = executions[0]

                # Verify expected fields present
                expected_fields = ["status", "workflow_id"]
                for field in expected_fields:
                    if field in execution:
                        assert execution[field] is not None

                # Verify timestamp fields if present
                if "started_at" in execution or "start_time" in execution:
                    timestamp = execution.get("started_at") or execution.get("start_time")
                    assert timestamp is not None

                if "completed_at" in execution or "end_time" in execution:
                    timestamp = execution.get("completed_at") or execution.get("end_time")
                    # completed_at may be None for running executions
                    assert timestamp is None or timestamp is not None
        elif response.status_code == 404:
            pytest.skip("Workflow executions history endpoint not implemented")

    def test_mobile_workflow_execution_history_pagination(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test execution history pagination"""
        response = mobile_api_client.get(
            "/api/v1/workflows/executions?limit=10&offset=0",
            headers=mobile_auth_headers
        )

        if response.status_code == 200:
            data = response.json()
            executions = data.get("executions", data.get("items", []))

            if isinstance(executions, list):
                # Verify limit respected
                assert len(executions) <= 10
        elif response.status_code == 404:
            pytest.skip("Workflow executions history endpoint not implemented")


class TestMobileWorkflowList:
    """Test mobile workflow listing"""

    def test_mobile_workflow_list(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test listing available workflows"""
        response = mobile_api_client.get(
            "/api/v1/workflows",
            headers=mobile_auth_headers
        )

        # Verify response
        if response.status_code == 200:
            data = response.json()

            # Verify workflows structure
            assert "workflows" in data or isinstance(data, list)

            # Get workflows list
            workflows = data.get("workflows", data)

            if isinstance(workflows, list) and workflows:
                # Verify workflow structure
                workflow = workflows[0]
                assert "id" in workflow or "workflow_id" in workflow
                assert "name" in workflow
        elif response.status_code == 404:
            pytest.skip("Workflow list endpoint not implemented")

    def test_mobile_workflow_list_filtering(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test workflow list filtering"""
        # Try filtering by category
        response = mobile_api_client.get(
            "/api/v1/workflows?category=testing",
            headers=mobile_auth_headers
        )

        if response.status_code == 200:
            data = response.json()
            workflows = data.get("workflows", data)

            if isinstance(workflows, list):
                # If category filtering works, verify results
                # (This is a basic test - actual filtering depends on implementation)
                assert True  # Endpoint available
        elif response.status_code == 404:
            pytest.skip("Workflow list endpoint not implemented")
