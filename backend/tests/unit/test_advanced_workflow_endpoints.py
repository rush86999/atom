"""
Unit tests for advanced_workflow_endpoints.py

Tests cover:
- Endpoint initialization and configuration
- Workflow CRUD operations (create, list, get, update)
- Workflow execution control (start, pause, resume, cancel)
- Workflow status and step management
- Template management
- Parameter validation
- Export/import functionality
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from datetime import datetime
from fastapi.testclient import TestClient
from fastapi import FastAPI
import sys
sys.path.insert(0, '/Users/rushiparikh/projects/atom/backend')

from core.advanced_workflow_endpoints import (
    router,
    CreateWorkflowRequest,
    StartWorkflowRequest,
    UpdateWorkflowRequest,
    WorkflowStepRequest,
    serialize_workflow
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def app():
    """Create a test FastAPI app"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create a test client"""
    return TestClient(app)


@pytest.fixture
def mock_state_manager():
    """Mock state manager"""
    manager = MagicMock()
    manager.load_state = MagicMock(return_value=None)
    manager.list_workflows = MagicMock(return_value=[])
    manager.save_state = MagicMock()
    return manager


@pytest.fixture
def mock_execution_engine():
    """Mock execution engine"""
    engine = MagicMock()
    engine.create_workflow = AsyncMock(return_value=Mock(
        workflow_id="test-workflow-123",
        name="Test Workflow",
        description="Test Description",
        version=1,
        category="general",
        tags=[],
        input_schema=[],
        steps=[],
        output_config=None,
        state="draft",
        current_step=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        created_by="test-user"
    ))
    engine.start_workflow = AsyncMock(return_value={"status": "started"})
    engine.pause_workflow = MagicMock(return_value=True)
    engine.resume_workflow = MagicMock(return_value={"status": "resumed"})
    engine.cancel_workflow = MagicMock(return_value=True)
    engine.get_workflow_status = MagicMock(return_value={"status": "running"})
    engine._get_missing_inputs = MagicMock(return_value=[])
    engine._execute_step = AsyncMock(return_value={"status": "success"})
    return engine


@pytest.fixture
def mock_template_manager():
    """Mock template manager"""
    manager = MagicMock()
    manager.list_templates = MagicMock(return_value=[])
    manager.create_template = MagicMock(return_value=Mock(
        template_id="template-123",
        name="Test Template"
    ))
    manager.create_workflow_from_template = MagicMock(return_value={})
    return manager


@pytest.fixture
def sample_workflow_request():
    """Sample workflow creation request"""
    return {
        "name": "Test Workflow",
        "description": "A test workflow for unit testing",
        "category": "testing",
        "tags": ["test", "unit"],
        "input_schema": [],
        "steps": [],
        "output_config": None
    }


@pytest.fixture
def sample_workflow_state():
    """Sample workflow state from database"""
    return {
        "workflow_id": "workflow-123",
        "name": "Existing Workflow",
        "description": "An existing workflow",
        "version": 1,
        "category": "general",
        "tags": [],
        "input_schema": [],
        "steps": [],
        "output_config": None,
        "state": "draft",
        "current_step": None,
        "created_at": "2026-02-13T12:00:00Z",
        "updated_at": "2026-02-13T12:00:00Z",
        "created_by": "test-user",
        "step_results": {},
        "execution_context": None
    }


# =============================================================================
# Apply mocks
# =============================================================================

@pytest.fixture(autouse=True)
def apply_mocks(mock_state_manager, mock_execution_engine, mock_template_manager):
    """Apply mocks to the module"""
    with patch('core.advanced_workflow_endpoints.state_manager', mock_state_manager):
        with patch('core.advanced_workflow_endpoints.execution_engine', mock_execution_engine):
            with patch('core.advanced_workflow_endpoints.template_manager', mock_template_manager):
                yield


# =============================================================================
# TEST CLASS: Helper Functions
# =============================================================================

class TestHelperFunctions:
    """Tests for helper functions"""

    def test_serialize_workflow_basic(self, sample_workflow_state):
        """Verify basic workflow serialization"""
        workflow = Mock(
            workflow_id="workflow-123",
            name="Test Workflow",
            description="Test Description",
            version=1,
            category="test",
            tags=["tag1", "tag2"],
            input_schema=[],
            steps=[],
            output_config=None,
            state="draft",
            current_step=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            created_by="test-user"
        )

        result = serialize_workflow(workflow)

        assert result["workflow_id"] == "workflow-123"
        assert result["name"] == "Test Workflow"
        assert result["description"] == "Test Description"
        assert result["version"] == 1
        assert result["category"] == "test"
        assert result["tags"] == ["tag1", "tag2"]
        assert result["state"] == "draft"
        assert result["created_by"] == "test-user"

    def test_serialize_workflow_with_steps(self):
        """Verify workflow serialization with steps"""
        workflow = Mock(
            workflow_id="workflow-123",
            name="Test Workflow",
            description="Test",
            version=1,
            category="test",
            tags=[],
            input_schema=[],
            steps=[
                Mock(step_id="step1", dict=lambda: {"step_id": "step1", "name": "Step 1"})
            ],
            output_config=None,
            state="draft",
            current_step="step1",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            created_by="test-user"
        )

        result = serialize_workflow(workflow)

        assert "steps" in result
        assert len(result["steps"]) == 1
        assert result["steps"][0]["step_id"] == "step1"


# =============================================================================
# TEST CLASS: Workflow CRUD Operations
# =============================================================================

class TestWorkflowCRUD:
    """Tests for workflow CRUD operations"""

    def test_create_workflow_success(self, client, sample_workflow_request, mock_execution_engine):
        """Verify successful workflow creation"""
        response = client.post("/workflows", json=sample_workflow_request)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "workflow_id" in data
        assert "workflow" in data

    def test_create_workflow_with_validation_error(self, client, mock_execution_engine):
        """Verify workflow creation with validation error"""
        mock_execution_engine.create_workflow.side_effect = Exception("Validation error")

        response = client.post("/workflows", json={
            "name": "Invalid Workflow",
            "description": "Test"
        })

        assert response.status_code == 400

    def test_list_workflows_empty(self, client, mock_state_manager):
        """Verify listing workflows when none exist"""
        mock_state_manager.list_workflows.return_value = []

        response = client.get("/workflows")

        assert response.status_code == 200
        data = response.json()
        assert "workflows" in data
        assert data["workflows"] == []

    def test_list_workflows_with_filters(self, client, mock_state_manager):
        """Verify listing workflows with filters"""
        mock_state_manager.list_workflows.return_value = [
            {
                "workflow_id": "workflow-1",
                "name": "Workflow 1",
                "state": "draft",
                "category": "testing"
            }
        ]

        response = client.get("/workflows?state=draft&category=testing")

        assert response.status_code == 200
        data = response.json()
        assert len(data["workflows"]) == 1

    def test_list_workflows_with_pagination(self, client, mock_state_manager):
        """Verify listing workflows with pagination"""
        mock_state_manager.list_workflows.return_value = [
            {"workflow_id": f"workflow-{i}", "name": f"Workflow {i}"}
            for i in range(5)
        ]

        response = client.get("/workflows?limit=3&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert data["offset"] == 0
        assert data["limit"] == 3

    def test_get_workflow_not_found(self, client, mock_state_manager):
        """Verify getting non-existent workflow returns 404"""
        mock_state_manager.load_state.return_value = None

        response = client.get("/workflows/nonexistent")

        assert response.status_code == 404

    def test_get_workflow_success(self, client, sample_workflow_state, mock_state_manager):
        """Verify getting existing workflow"""
        mock_state_manager.load_state.return_value = sample_workflow_state

        response = client.get("/workflows/workflow-123")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "workflow" in data


# =============================================================================
# TEST CLASS: Workflow Execution Control
# =============================================================================

class TestWorkflowExecution:
    """Tests for workflow execution control"""

    def test_start_workflow_success(self, client, mock_state_manager, mock_execution_engine):
        """Verify successful workflow start"""
        mock_state_manager.load_state.return_value = {
            "workflow_id": "workflow-123",
            "input_schema": [],
            "steps": [],
            "user_inputs": {}
        }

        response = client.post("/workflows/workflow-123/start", json={
            "workflow_id": "workflow-123",
            "inputs": {}
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_start_workflow_not_found(self, client, mock_state_manager):
        """Verify starting non-existent workflow returns 404"""
        mock_state_manager.load_state.return_value = None

        response = client.post("/workflows/nonexistent/start", json={
            "workflow_id": "nonexistent",
            "inputs": {}
        })

        assert response.status_code == 404

    def test_pause_workflow_success(self, client, mock_execution_engine):
        """Verify successful workflow pause"""
        mock_execution_engine.pause_workflow.return_value = True

        response = client.post("/workflows/workflow-123/pause")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_pause_workflow_cannot_pause(self, client, mock_execution_engine):
        """Verify pausing workflow that cannot be paused"""
        mock_execution_engine.pause_workflow.return_value = False

        response = client.post("/workflows/workflow-123/pause")

        assert response.status_code == 400

    def test_resume_workflow_success(self, client, mock_execution_engine, mock_state_manager):
        """Verify successful workflow resume"""
        mock_state_manager.load_state.return_value = {
            "state": "paused",
            "user_inputs": {}
        }
        mock_execution_engine.resume_workflow.return_value = {"status": "resumed"}

        response = client.post("/workflows/workflow-123/resume", json={
            "inputs": {}
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_cancel_workflow_success(self, client, mock_execution_engine):
        """Verify successful workflow cancellation"""
        mock_execution_engine.cancel_workflow.return_value = True

        response = client.post("/workflows/workflow-123/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_cancel_workflow_cannot_cancel(self, client, mock_execution_engine):
        """Verify cancelling workflow that cannot be cancelled"""
        mock_execution_engine.cancel_workflow.return_value = False

        response = client.post("/workflows/workflow-123/cancel")

        assert response.status_code == 400


# =============================================================================
# TEST CLASS: Workflow Status and Steps
# =============================================================================

class TestWorkflowStatusAndSteps:
    """Tests for workflow status and step management"""

    def test_get_workflow_status_success(self, client, mock_execution_engine):
        """Verify getting workflow status"""
        mock_execution_engine.get_workflow_status.return_value = {
            "status": "running",
            "current_step": "step1",
            "progress": 0.5
        }

        response = client.get("/workflows/workflow-123/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["workflow_status"]["status"] == "running"

    def test_get_workflow_status_not_found(self, client, mock_execution_engine):
        """Verify getting status for non-existent workflow"""
        mock_execution_engine.get_workflow_status.return_value = None

        response = client.get("/workflows/nonexistent/status")

        assert response.status_code == 404

    def test_get_workflow_step_success(self, client, sample_workflow_state, mock_state_manager):
        """Verify getting specific workflow step"""
        sample_workflow_state["steps"] = [
            {"step_id": "step1", "name": "Step 1", "input_parameters": []}
        ]
        mock_state_manager.load_state.return_value = sample_workflow_state

        response = client.get("/workflows/workflow-123/step/step1")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "step" in data

    def test_get_workflow_step_not_found(self, client, mock_state_manager):
        """Verify getting non-existent step returns 404"""
        mock_state_manager.load_state.return_value = {
            "workflow_id": "workflow-123",
            "steps": []
        }

        response = client.get("/workflows/workflow-123/step/nonexistent")

        assert response.status_code == 404

    def test_execute_workflow_step_success(self, client, sample_workflow_state, mock_state_manager, mock_execution_engine):
        """Verify executing specific workflow step"""
        sample_workflow_state["steps"] = [
            {"step_id": "step1", "name": "Step 1", "input_parameters": []}
        ]
        sample_workflow_state["user_inputs"] = {}
        sample_workflow_state["step_results"] = {}
        mock_state_manager.load_state.return_value = sample_workflow_state
        mock_execution_engine._execute_step.return_value = {"status": "completed"}

        response = client.post("/workflows/workflow-123/step/step1/execute", json={
            "step_id": "step1",
            "inputs": {}
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_get_required_inputs_success(self, client, sample_workflow_state, mock_state_manager, mock_execution_engine):
        """Verify getting required inputs for workflow"""
        mock_state_manager.load_state.return_value = sample_workflow_state
        mock_execution_engine._get_missing_inputs.return_value = []

        response = client.get("/workflows/workflow-123/inputs/required")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "required_inputs" in data


# =============================================================================
# TEST CLASS: Template Management
# =============================================================================

class TestTemplateManagement:
    """Tests for workflow template management"""

    def test_list_workflow_templates(self, client, mock_template_manager):
        """Verify listing workflow templates"""
        mock_template_manager.list_templates.return_value = [
            Mock(
                template_id="template-1",
                name="Template 1",
                description="Test template",
                category="testing",
                input_schema=[],
                steps=[],
                tags=[],
                dict=lambda: {
                    "template_id": "template-1",
                    "name": "Template 1",
                    "description": "Test template",
                    "category": "testing",
                    "input_schema": [],
                    "steps": [],
                    "tags": []
                }
            )
        ]

        response = client.get("/workflows/templates")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1

    def test_list_templates_with_filters(self, client, mock_template_manager):
        """Verify listing templates with filters"""
        mock_template_manager.list_templates.return_value = []

        response = client.get("/workflows/templates?category=testing&active_only=true")

        assert response.status_code == 200

    def test_create_workflow_template_success(self, client, mock_template_manager):
        """Verify creating workflow template"""
        mock_template_manager.create_template.return_value = Mock(
            template_id="template-123",
            name="New Template",
            dict=lambda: {"template_id": "template-123", "name": "New Template"}
        )

        response = client.post("/workflows/templates", json={
            "template_id": "template-123",
            "name": "New Template",
            "description": "Test template",
            "category": "testing"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "template_id" in data

    def test_create_workflow_from_template_success(self, client, mock_template_manager, mock_execution_engine):
        """Verify creating workflow from template"""
        mock_template_manager.create_workflow_from_template.return_value = {
            "workflow_id": "workflow-from-template",
            "name": "Workflow from Template"
        }
        mock_execution_engine.create_workflow = AsyncMock(return_value=Mock(
            workflow_id="workflow-from-template",
            name="Workflow from Template",
            dict=lambda: {"workflow_id": "workflow-from-template"}
        ))

        response = client.post("/workflows/from-template?template_id=template-123", json={
            "name": "My Workflow"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_create_workflow_from_template_not_found(self, client, mock_template_manager):
        """Verify creating workflow from non-existent template"""
        mock_template_manager.create_workflow_from_template.side_effect = ValueError("Template not found")

        response = client.post("/workflows/from-template?template_id=nonexistent", json={})

        assert response.status_code == 404


# =============================================================================
# TEST CLASS: Parameter Validation
# =============================================================================

class TestParameterValidation:
    """Tests for parameter validation endpoints"""

    def test_get_parameter_types(self, client):
        """Verify getting available parameter types"""
        response = client.get("/workflows/parameter-types")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have parameter types like string, number, boolean, etc.

    def test_validate_parameters_success(self, client):
        """Verify validating valid parameters"""
        response = client.post("/workflows/validate-parameters", json={
            "parameters": [
                {"name": "param1", "type": "string", "required": True}
            ],
            "inputs": {
                "param1": "test value"
            }
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "validation_results" in data
        assert data["all_valid"] is True

    def test_validate_parameters_invalid(self, client):
        """Verify validating invalid parameters"""
        response = client.post("/workflows/validate-parameters", json={
            "parameters": [
                {"name": "param1", "type": "string", "required": True}
            ],
            "inputs": {}
            # Missing required param1
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        # param1 should be invalid since it's missing
        assert "param1" in data["validation_results"]


# =============================================================================
# TEST CLASS: Export/Import
# =============================================================================

class TestExportImport:
    """Tests for workflow export/import functionality"""

    def test_export_workflow_success(self, client, sample_workflow_state, mock_state_manager):
        """Verify exporting workflow definition"""
        mock_state_manager.load_state.return_value = sample_workflow_state

        response = client.get("/workflows/workflow-123/export")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "workflow_definition" in data
        # Execution-specific data should be removed
        assert "step_results" not in data["workflow_definition"]
        assert "execution_context" not in data["workflow_definition"]

    def test_export_workflow_not_found(self, client, mock_state_manager):
        """Verify exporting non-existent workflow returns 404"""
        mock_state_manager.load_state.return_value = None

        response = client.get("/workflows/nonexistent/export")

        assert response.status_code == 404

    def test_import_workflow_success(self, client, mock_execution_engine):
        """Verify importing workflow definition"""
        mock_execution_engine.create_workflow = AsyncMock(return_value=Mock(
            workflow_id="imported-workflow",
            name="Imported Workflow",
            dict=lambda: {"workflow_id": "imported-workflow"}
        ))

        response = client.post("/workflows/import", json={
            "workflow_id": "original-workflow",
            "name": "Original Workflow",
            "steps": []
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "workflow_id" in data
        # Workflow ID should be changed to imported_*
        assert data["workflow_id"].startswith("imported_")


# =============================================================================
# TEST CLASS: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling"""

    def test_create_workflow_with_empty_name(self, client, mock_execution_engine):
        """Verify creating workflow with empty name"""
        mock_execution_engine.create_workflow.side_effect = ValueError("Name cannot be empty")

        response = client.post("/workflows", json={
            "name": "",
            "description": "Test"
        })

        assert response.status_code == 400

    def test_get_workflow_with_invalid_id(self, client):
        """Verify getting workflow with invalid ID format"""
        response = client.get("/workflows/invalid-id-format")

        # Should handle gracefully (either 404 or 200 depending on implementation)
        assert response.status_code in [200, 404]

    def test_list_workflows_with_invalid_sort_order(self, client, mock_state_manager):
        """Verify listing workflows with invalid sort order"""
        mock_state_manager.list_workflows.return_value = []

        # Should default to valid sort order
        response = client.get("/workflows?sort_order=invalid")

        assert response.status_code == 200

    def test_execute_step_with_invalid_workflow_id(self, client, mock_state_manager):
        """Verify executing step with non-existent workflow"""
        mock_state_manager.load_state.return_value = None

        response = client.post("/workflows/nonexistent/step/step1/execute", json={
            "step_id": "step1",
            "inputs": {}
        })

        assert response.status_code == 404


# =============================================================================
# TEST CLASS: Request Models
# =============================================================================

class TestRequestModels:
    """Tests for Pydantic request models"""

    def test_create_workflow_request_model(self):
        """Verify CreateWorkflowRequest model validation"""
        request = CreateWorkflowRequest(
            name="Test Workflow",
            description="Test",
            category="general",
            tags=["test"],
            input_schema=[],
            steps=[],
            output_config=None
        )

        assert request.name == "Test Workflow"
        assert request.category == "general"
        assert request.tags == ["test"]

    def test_start_workflow_request_model(self):
        """Verify StartWorkflowRequest model validation"""
        request = StartWorkflowRequest(
            workflow_id="workflow-123",
            inputs={"param1": "value1"}
        )

        assert request.workflow_id == "workflow-123"
        assert request.inputs == {"param1": "value1"}

    def test_workflow_step_request_model(self):
        """Verify WorkflowStepRequest model validation"""
        request = WorkflowStepRequest(
            step_id="step1",
            inputs={"input1": "value1"}
        )

        assert request.step_id == "step1"
        assert request.inputs == {"input1": "value1"}
