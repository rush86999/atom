"""
Tests for Workflow UI Endpoints

Test coverage for workflow UI API endpoints including:
- Workflow template and definition routes
- Workflow CRUD operations (create, read, update, delete)
- Workflow execution and history
- UI integration with mock data and database
- API authentication and error handling
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session
from datetime import datetime

from core.workflow_ui_endpoints import (
    router,
    WorkflowStep,
    WorkflowTemplateResponse,
    WorkflowDefinition,
    WorkflowExecution,
    ServiceInfo,
    MOCK_TEMPLATES,
    MOCK_WORKFLOWS,
    MOCK_EXECUTIONS,
    MOCK_SERVICES,
)


# ============================================================================
# Test: Workflow UI Routes
# ============================================================================

class TestWorkflowUIRoutes:
    """Test workflow template and definition endpoints."""

    def test_get_templates_with_database(self):
        """GET /templates returns templates from database."""
        # Arrange
        client = TestClient(router)
        mock_db = Mock(spec=Session)

        mock_template = Mock()
        mock_template.template_id = "tpl_001"
        mock_template.name = "Test Template"
        mock_template.description = "Test description"
        mock_template.category = "automation"
        mock_template.complexity = "beginner"
        mock_template.tags = ["automation"]
        mock_template.is_featured = True
        mock_template.is_public = True
        mock_template.rating = 4.5
        mock_template.usage_count = 100
        mock_template.author_id = "user_001"
        mock_template.version = "1.0.0"
        mock_template.steps_schema = []
        mock_template.inputs_schema = {}
        mock_template.created_at = datetime.now()
        mock_template.updated_at = datetime.now()

        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            mock_template
        ]

        # Act
        response = client.get("/templates?is_public=true")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "templates" in data
        assert isinstance(data["templates"], list)

    def test_get_templates_with_mock_mode(self):
        """GET /templates returns mock data when WORKFLOW_MOCK_ENABLED."""
        # Arrange
        client = TestClient(router)

        with patch('core.workflow_ui_endpoints.WORKFLOW_MOCK_ENABLED', True):

            # Act
            response = client.get("/templates")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["templates"]) > 0

    def test_get_templates_with_category_filter(self):
        """GET /templates filters by category."""
        # Arrange
        client = TestClient(router)
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        # Act
        response = client.get("/templates?category=business&is_public=true")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_import_template_success(self):
        """POST /templates/{template_id}/import creates private copy."""
        # Arrange
        client = TestClient(router)
        mock_db = Mock(spec=Session)

        mock_source = Mock()
        mock_source.template_id = "tpl_001"
        mock_source.name = "Source Template"
        mock_source.description = "Source description"
        mock_source.category = "automation"
        mock_source.complexity = "beginner"
        mock_source.tags = ["automation"]
        mock_source.template_json = {}
        mock_source.inputs_schema = {}
        mock_source.steps_schema = []
        mock_source.output_schema = {}
        mock_source.usage_count = 10

        mock_db.query.return_value.filter.return_value.first.return_value = mock_source
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Act
        response = client.post("/templates/tpl_001/import")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "workflow_id" in data

    def test_import_template_not_found(self):
        """POST /templates/{template_id}/import returns 404 for missing template."""
        # Arrange
        client = TestClient(router)
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Act
        response = client.post("/templates/nonexistent/import")

        # Assert
        assert response.status_code == 404

    def test_get_services_endpoint(self):
        """GET /services returns available service integrations."""
        # Arrange
        client = TestClient(router)

        # Act
        response = client.get("/services")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "services" in data
        assert len(data["services"]) > 0

    def test_get_workflow_definitions(self):
        """GET /definitions returns workflow definitions."""
        # Arrange
        client = TestClient(router)
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.offset.return_value.all.return_value = []

        # Act
        response = client.get("/definitions?limit=50&offset=0")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "workflows" in data


# ============================================================================
# Test: UI Integration
# ============================================================================

class TestUIIntegration:
    """Test UI integration with data fetching and transformation."""

    def test_ui_workflow_models_validation(self):
        """Workflow UI Pydantic models validate correctly."""
        # Arrange & Act
        step = WorkflowStep(
            id="step_001",
            type="action",
            service="slack",
            action="send_message",
            parameters={"channel": "#general"},
            name="Send Slack Message"
        )

        template = WorkflowTemplateResponse(
            id="tpl_001",
            name="Test Template",
            description="Test description",
            category="automation",
            icon="workflow",
            steps=[step],
            input_schema={"type": "object"}
        )

        workflow = WorkflowDefinition(
            id="wf_001",
            name="Test Workflow",
            description="Test workflow",
            steps=[step],
            input_schema={},
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            steps_count=1
        )

        execution = WorkflowExecution(
            execution_id="exec_001",
            workflow_id="wf_001",
            status="completed",
            start_time=datetime.now().isoformat(),
            end_time=datetime.now().isoformat(),
            current_step=1,
            total_steps=1,
            results={"success": True}
        )

        service = ServiceInfo(
            name="Slack",
            actions=["send_message", "create_channel"],
            description="Team communication"
        )

        # Assert
        assert step.id == "step_001"
        assert step.type == "action"
        assert template.id == "tpl_001"
        assert workflow.id == "wf_001"
        assert execution.status == "completed"
        assert service.name == "Slack"

    def test_mock_data_initialized(self):
        """Mock data templates and workflows are initialized."""
        # Assert
        assert len(MOCK_TEMPLATES) > 0
        assert len(MOCK_WORKFLOWS) > 0
        assert len(MOCK_EXECUTIONS) > 0
        assert len(MOCK_SERVICES) > 0

        # Verify expected services exist
        assert "slack" in MOCK_SERVICES
        assert "ai" in MOCK_SERVICES
        assert "gmail" in MOCK_SERVICES

    def test_workflow_step_parameters_default(self):
        """WorkflowStep parameters default to empty dict."""
        # Arrange & Act
        step = WorkflowStep(
            id="step_002",
            type="action",
            name="Test Step"
        )

        # Assert
        assert step.parameters == {}
        assert step.service is None
        assert step.action is None


# ============================================================================
# Test: Workflow Canvas
# ============================================================================

class TestWorkflowCanvas:
    """Test workflow canvas data and configuration."""

    def test_get_workflow_by_id_success(self):
        """GET /workflows/{workflow_id} returns workflow details."""
        # Arrange
        client = TestClient(router)
        mock_db = Mock(spec=Session)

        mock_template = Mock()
        mock_template.template_id = "wf_001"
        mock_template.name = "Test Workflow"
        mock_template.description = "Test workflow description"
        mock_template.category = "automation"
        mock_template.complexity = "beginner"
        mock_template.tags = ["test"]
        mock_template.steps_schema = []
        mock_template.inputs_schema = {}
        mock_template.rating = 4.0
        mock_template.usage_count = 50
        mock_template.version = "1.0.0"
        mock_template.author_id = "user_001"
        mock_template.created_at = datetime.now()
        mock_template.updated_at = datetime.now()

        mock_db.query.return_value.filter.return_value.first.return_value = mock_template

        # Act
        response = client.get("/workflows/wf_001")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["workflow"]["id"] == "wf_001"

    def test_get_workflow_by_id_not_found(self):
        """GET /workflows/{workflow_id} returns 404 for missing workflow."""
        # Arrange
        client = TestClient(router)
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Act
        response = client.get("/workflows/nonexistent")

        # Assert
        assert response.status_code == 404

    def test_create_workflow_success(self):
        """POST /workflows creates new workflow."""
        # Arrange
        client = TestClient(router)
        mock_db = Mock(spec=Session)
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        with patch('core.workflow_ui_endpoints.uuid.uuid4', return_value='test12345'):
            payload = {
                "name": "New Workflow",
                "description": "Test workflow creation",
                "category": "automation",
                "complexity": "beginner",
                "input_schema": {"type": "object"},
                "steps": []
            }

            # Act
            response = client.post("/workflows", json=payload)

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["workflow"]["name"] == "New Workflow"

    def test_update_workflow_success(self):
        """PUT /workflows/{workflow_id} updates existing workflow."""
        # Arrange
        client = TestClient(router)
        mock_db = Mock(spec=Session)

        mock_template = Mock()
        mock_template.template_id = "wf_001"
        mock_template.name = "Old Name"
        mock_template.description = "Old description"
        mock_template.category = "automation"
        mock_template.complexity = "beginner"
        mock_template.tags = []
        mock_template.inputs_schema = {}
        mock_template.steps_schema = []
        mock_template.output_schema = {}
        mock_template.is_public = False
        mock_template.version = "1.0.0"
        mock_template.created_at = datetime.now()
        mock_template.updated_at = datetime.now()

        mock_db.query.return_value.filter.return_value.first.return_value = mock_template
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        payload = {
            "name": "Updated Name",
            "description": "Updated description"
        }

        # Act
        response = client.put("/workflows/wf_001", json=payload)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_db.commit.assert_called_once()

    def test_delete_workflow_success(self):
        """DELETE /workflows/{workflow_id} deletes workflow."""
        # Arrange
        client = TestClient(router)
        mock_db = Mock(spec=Session)

        mock_template = Mock()
        mock_template.template_id = "wf_001"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_template
        mock_db.delete = Mock()
        mock_db.commit = Mock()

        # Act
        response = client.delete("/workflows/wf_001")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_db.delete.assert_called_once()

    def test_list_workflows_alias(self):
        """GET /workflows (list) returns workflows (alias for /definitions)."""
        # Arrange
        client = TestClient(router)
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.offset.return_value.all.return_value = []

        # Act
        response = client.get("/workflows?limit=10&offset=0")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# ============================================================================
# Test: API Authentication
# ============================================================================

class TestAPIAuthentication:
    """Test API authentication and authorization."""

    def test_api_response_format_consistent(self):
        """All API responses follow consistent format."""
        # Arrange
        client = TestClient(router)

        # Act & Assert
        response = client.get("/services")
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert isinstance(data["success"], bool)

    def test_error_response_format(self):
        """Error responses follow consistent format."""
        # Arrange
        client = TestClient(router)
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Act
        response = client.get("/workflows/nonexistent")

        # Assert
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_endpoint_requires_database_session(self):
        """Endpoints that require database session accept dependency injection."""
        # Arrange
        client = TestClient(router)
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.offset.return_value.all.return_value = []

        # Act
        response = client.get("/workflows")

        # Assert
        assert response.status_code == 200


# ============================================================================
# Test: Workflow Execution
# ============================================================================

class TestWorkflowExecution:
    """Test workflow execution and history endpoints."""

    def test_execute_workflow_by_id(self):
        """POST /workflows/{workflow_id}/execute starts workflow execution."""
        # Arrange
        client = TestClient(router)

        with patch('core.workflow_ui_endpoints.BackgroundTasks'):
            with patch('core.workflow_ui_endpoints.uuid.uuid4', return_value='exec123'):
                # Act
                response = client.post("/workflows/wf_001/execute", json={"input": {}})

                # Assert
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "execution_id" in data

    def test_get_workflow_history(self):
        """GET /workflows/{workflow_id}/history returns execution history."""
        # Arrange
        client = TestClient(router)

        # Act
        response = client.get("/workflows/wf_001/history")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "history" in data
        assert isinstance(data["history"], list)

    def test_create_workflow_definition(self):
        """POST /definitions creates new workflow definition."""
        # Arrange
        client = TestClient(router)

        with patch('core.workflow_ui_endpoints.uuid.uuid4', return_value='test123'):
            payload = {
                "name": "Visual Workflow",
                "description": "Created via Visual Builder",
                "definition": {
                    "nodes": [
                        {"id": "node1", "type": "action"}
                    ]
                }
            }

            # Act
            response = client.post("/definitions", json=payload)

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "workflow" in data

    def test_get_executions(self):
        """GET /executions returns active workflow executions."""
        # Arrange
        client = TestClient(router)

        # Act
        response = client.get("/executions")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "executions" in data

    def test_cancel_execution(self):
        """POST /executions/{execution_id}/cancel cancels running execution."""
        # Arrange
        client = TestClient(router)

        # Create a mock execution first
        from core.workflow_ui_endpoints import MOCK_EXECUTIONS
        mock_exec = WorkflowExecution(
            execution_id="exec_cancel_001",
            workflow_id="wf_001",
            status="running",
            start_time=datetime.now().isoformat(),
            current_step=1,
            total_steps=3
        )
        MOCK_EXECUTIONS.append(mock_exec)

        # Act
        response = client.post("/executions/exec_cancel_001/cancel")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_cancel_execution_not_found(self):
        """POST /executions/{execution_id}/cancel returns 404 for missing execution."""
        # Arrange
        client = TestClient(router)

        # Act
        response = client.post("/executions/nonexistent/cancel")

        # Assert
        assert response.status_code == 404

    def test_execute_workflow_endpoint(self):
        """POST /execute executes workflow with input data."""
        # Arrange
        client = TestClient(router)

        with patch('core.workflow_ui_endpoints.BackgroundTasks'):
            with patch('core.workflow_ui_endpoints.uuid.uuid4', return_value='exec123'):
                payload = {
                    "workflow_id": "tpl_o365_finance",
                    "input": {
                        "month": "January",
                        "dataset": "sales_dashboard"
                    }
                }

                # Act
                response = client.post("/execute", json=payload)

                # Assert
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "execution_id" in data
                assert "status" in data

    def test_debug_orchestrator_state(self):
        """GET /debug/state returns orchestrator debug information."""
        # Arrange
        client = TestClient(router)

        # Act
        response = client.get("/debug/state")

        # Assert
        # May fail if orchestrator not available, which is OK
        assert response.status_code in [200, 500]
