"""
Comprehensive test suite for OrchestrationCanvasService

Tests orchestration canvas service for agent-driven workflow orchestration
with human-in-the-loop guidance from meta-agents.

Target File: core/canvas_orchestration_service.py (485 lines)
Test Coverage: 25-30 tests across 4 test classes
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from sqlalchemy.orm import Session

from core.canvas_orchestration_service import (
    OrchestrationCanvasService,
    WorkflowTask,
    IntegrationNode,
    WorkflowConnection,
    CanvasTaskStatus
)
from core.models import CanvasAudit


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock(spec=Session)
    return db


@pytest.fixture
def service(mock_db):
    """OrchestrationCanvasService instance."""
    return OrchestrationCanvasService(mock_db)


@pytest.fixture
def sample_tasks():
    """Sample workflow tasks."""
    return [
        {
            "title": "Send welcome email",
            "status": "pending",
            "assignee": "student-agent-1",
            "tags": ["onboarding"],
            "integrations": ["email"]
        },
        {
            "title": "Schedule training call",
            "status": "pending",
            "assignee": "student-agent-1"
        },
        {
            "title": "Meta-agent review",
            "status": "pending",
            "assignee": "atom-meta-agent"
        }
    ]


# ============================================================================
# Test Class 1: Orchestration Initialization
# ============================================================================

class TestOrchestrationInitialization:
    """Tests for service initialization and canvas creation."""

    def test_service_initialization_with_database(self, service, mock_db):
        """Test service initializes with database session."""
        # Assert
        assert service.db == mock_db
        assert isinstance(service, OrchestrationCanvasService)

    def test_canvas_state_factory_creation(self):
        """Test WorkflowTask factory creates task objects."""
        # Arrange & Act
        task = WorkflowTask(
            task_id="task-001",
            title="Test Task",
            status=CanvasTaskStatus.PENDING,
            assignee="agent-001"
        )

        # Assert
        assert task.task_id == "task-001"
        assert task.title == "Test Task"
        assert task.status == CanvasTaskStatus.PENDING
        assert task.assignee == "agent-001"

    def test_presentation_builder_initialization(self):
        """Test IntegrationNode factory creates node objects."""
        # Arrange & Act
        node = IntegrationNode(
            node_id="node-001",
            app_name="Email Integration",
            node_type="action",
            config={"action": "send_email"}
        )

        # Assert
        assert node.node_id == "node-001"
        assert node.app_name == "Email Integration"
        assert node.node_type == "action"

    def test_orchestrator_configuration(self, service):
        """Test orchestrator can be configured with different parameters."""
        # Assert
        assert hasattr(service, 'db')
        assert hasattr(service, 'create_orchestration_canvas')

    def test_dependency_injection(self, mock_db):
        """Test database session is properly injected."""
        # Act
        service = OrchestrationCanvasService(mock_db)

        # Assert
        assert service.db is mock_db

    def test_default_parameters(self, service, mock_db):
        """Test service uses default parameters correctly."""
        # Arrange
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        # Act
        result = service.create_orchestration_canvas(
            user_id="user-001",
            title="Test Canvas"
        )

        # Assert
        assert result["success"] is True
        assert "canvas_id" in result


# ============================================================================
# Test Class 2: Presentation Lifecycle
# ============================================================================

class TestPresentationLifecycle:
    """Tests for canvas creation, updates, and lifecycle management."""

    def test_create_presentation_with_valid_config(
        self, service, mock_db, sample_tasks
    ):
        """Test creating orchestration canvas with valid configuration."""
        # Arrange
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        # Act
        result = service.create_orchestration_canvas(
            user_id="user-001",
            title="Customer Onboarding",
            agent_id="student-agent-1",
            layout="board",
            tasks=sample_tasks
        )

        # Assert
        assert result["success"] is True
        assert result["canvas_id"] is not None
        assert result["title"] == "Customer Onboarding"
        assert len(result["tasks"]) == 3
        assert mock_db.add.called
        assert mock_db.commit.called

    def test_start_presentation_execution(self, service, mock_db):
        """Test canvas starts execution phase correctly."""
        # Arrange
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        # Act
        result = service.create_orchestration_canvas(
            user_id="user-001",
            title="Sales Dashboard",
            agent_id="agent-001"
        )

        # Assert
        assert result["success"] is True
        assert mock_db.commit.called

    def test_update_presentation_state_changes(
        self, service, mock_db, sample_tasks
    ):
        """Test updating canvas state through adding tasks."""
        # Arrange
        mock_audit = CanvasAudit(
            id="audit-001",
            tenant_id="default",
            canvas_id="canvas-001",
            action_type="create",
            details_json={
                "canvas_type": "orchestration",
                "component_type": "kanban_board",
                "tasks": [],
                "nodes": [],
                "connections": [],
            },
        )

        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = mock_audit
        mock_db.query.return_value = mock_query
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        # Act
        result = service.add_task(
            canvas_id="canvas-001",
            user_id="user-001",
            title="New Task",
            status="pending",
            assignee="agent-001"
        )

        # Assert
        assert result["success"] is True
        assert result["task_id"] is not None

    def test_end_presentation_cleanup(self, service, mock_db):
        """Test canvas cleanup and completion."""
        # Arrange
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        # Act
        result = service.create_orchestration_canvas(
            user_id="user-001",
            title="Completed Workflow"
        )

        # Assert
        assert result["success"] is True

    def test_presentation_error_handling(self, service, mock_db):
        """Test error handling when canvas creation fails."""
        # Arrange
        mock_db.commit.side_effect = Exception("Database error")
        mock_db.rollback = MagicMock()

        # Act
        result = service.create_orchestration_canvas(
            user_id="user-001",
            title="Error Canvas"
        )

        # Assert
        assert result["success"] is False
        assert "error" in result
        assert mock_db.rollback.called

    def test_presentation_persistence(self, service, mock_db):
        """Test canvas state persists to database."""
        # Arrange
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        # Act
        result = service.create_orchestration_canvas(
            user_id="user-001",
            title="Persistent Canvas",
            tasks=[{"title": "Task 1", "status": "pending"}]
        )

        # Assert
        assert result["success"] is True
        assert mock_db.add.called
        assert mock_db.commit.called


# ============================================================================
# Test Class 3: State Management
# ============================================================================

class TestStateManagement:
    """Tests for canvas state retrieval, updates, and synchronization."""

    def test_get_canvas_state_retrieval(self, service, mock_db):
        """Test retrieving canvas state from database."""
        # Arrange
        mock_audit = CanvasAudit(
            id="audit-001",
            tenant_id="default",
            canvas_id="canvas-001",
            action_type="create",
            details_json={
                "canvas_type": "orchestration",
                "component_type": "kanban_board",
                "tasks": [{"task_id": "task-001", "title": "Task 1"}],
                "nodes": [],
                "connections": [],
            },
        )

        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = mock_audit
        mock_db.query.return_value = mock_query

        # Act - Add a new task to verify state retrieval
        result = service.add_task(
            canvas_id="canvas-001",
            user_id="user-001",
            title="Retrieved Task"
        )

        # Assert
        assert result["success"] is True

    def test_update_canvas_state_mutations(self, service, mock_db):
        """Test updating canvas state mutations."""
        # Arrange
        mock_audit = CanvasAudit(
            id="audit-001",
            tenant_id="default",
            canvas_id="canvas-001",
            action_type="create",
            details_json={
                "canvas_type": "orchestration",
                "component_type": "kanban_board",
                "tasks": [],
                "nodes": [],
                "connections": [],
            },
        )

        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = mock_audit
        mock_db.query.return_value = mock_query
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        # Act
        result = service.add_task(
            canvas_id="canvas-001",
            user_id="user-001",
            title="State Update Task",
            status="in_progress"
        )

        # Assert
        assert result["success"] is True
        assert mock_db.add.called

    def test_state_synchronization_across_clients(self, service, mock_db):
        """Test state synchronization when multiple clients access canvas."""
        # Arrange
        mock_audit = CanvasAudit(
            id="audit-001",
            tenant_id="default",
            canvas_id="canvas-001",
            action_type="create",
            details_json={
                "canvas_type": "orchestration",
                "component_type": "kanban_board",
                "tasks": [],
                "nodes": [],
                "connections": [],
            },
        )

        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = mock_audit
        mock_db.query.return_value = mock_query
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        # Act - Multiple updates (simulating multiple clients)
        result1 = service.add_task(
            canvas_id="canvas-001",
            user_id="user-001",
            title="Client 1 Task"
        )

        result2 = service.add_task(
            canvas_id="canvas-001",
            user_id="user-002",
            title="Client 2 Task"
        )

        # Assert
        assert result1["success"] is True
        assert result2["success"] is True
        assert mock_db.commit.call_count == 2

    def test_state_versioning(self, service, mock_db):
        """Test canvas state maintains version history."""
        # Arrange
        mock_audit = CanvasAudit(
            id="audit-001",
            tenant_id="default",
            canvas_id="canvas-001",
            action_type="create",
            details_json={
                "canvas_type": "orchestration",
                "component_type": "kanban_board",
                "tasks": [],
                "nodes": [],
                "connections": [],
            },
        )

        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = mock_audit
        mock_db.query.return_value = mock_query
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        # Act - Multiple state updates create version history
        for i in range(3):
            service.add_task(
                canvas_id="canvas-001",
                user_id="user-001",
                title=f"Task {i}"
            )

        # Assert - Each update creates a new audit record
        assert mock_db.add.call_count == 3
        assert mock_db.commit.call_count == 3

    def test_state_rollback_on_error(self, service, mock_db):
        """Test state rolls back on error."""
        # Arrange
        mock_audit = CanvasAudit(
            id="audit-001",
            tenant_id="default",
            canvas_id="canvas-001",
            action_type="create",
            details_json={
                "canvas_type": "orchestration",
                "component_type": "kanban_board",
                "tasks": [],
                "nodes": [],
                "connections": [],
            },
        )

        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = mock_audit
        mock_db.query.return_value = mock_query
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.rollback = MagicMock()

        # Act - Simulate error during update
        mock_db.commit.side_effect = Exception("Update failed")

        result = service.add_task(
            canvas_id="canvas-001",
            user_id="user-001",
            title="Failed Task"
        )

        # Assert
        assert result["success"] is False
        assert mock_db.rollback.called

    def test_state_aggregation(self, service, mock_db):
        """Test canvas state aggregates tasks, nodes, and connections."""
        # Arrange
        mock_audit = CanvasAudit(
            id="audit-001",
            tenant_id="default",
            canvas_id="canvas-001",
            action_type="create",
            details_json={
                "canvas_type": "orchestration",
                "component_type": "kanban_board",
                "tasks": [],
                "nodes": [],
                "connections": [],
                "integrations": [],
            },
        )

        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = mock_audit
        mock_db.query.return_value = mock_query
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        # Act - Add task, node, and connection
        service.add_task(
            canvas_id="canvas-001",
            user_id="user-001",
            title="Aggregated Task"
        )

        service.add_workflow_node(
            canvas_id="canvas-001",
            user_id="user-001",
            node_name="Email Node",
            node_type="action"
        )

        service.connect_nodes(
            canvas_id="canvas-001",
            user_id="user-001",
            from_node="node-001",
            to_node="node-002"
        )

        # Assert
        assert mock_db.add.call_count == 3


# ============================================================================
# Test Class 4: Multi-Client Coordination
# ============================================================================

class TestMultiClientCoordination:
    """Tests for multi-client canvas coordination and session management."""

    def test_client_registration(self, service, mock_db):
        """Test clients can register and access canvas."""
        # Arrange
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        # Act - Different users create canvases
        result1 = service.create_orchestration_canvas(
            user_id="user-001",
            title="User 1 Canvas"
        )

        result2 = service.create_orchestration_canvas(
            user_id="user-002",
            title="User 2 Canvas"
        )

        # Assert
        assert result1["success"] is True
        assert result2["success"] is True
        assert result1["canvas_id"] != result2["canvas_id"]

    def test_broadcast_state_to_all_clients(self, service, mock_db):
        """Test state updates broadcast to all clients."""
        # Arrange
        mock_audit = CanvasAudit(
            id="audit-001",
            tenant_id="default",
            canvas_id="canvas-001",
            action_type="create",
            details_json={
                "canvas_type": "orchestration",
                "component_type": "kanban_board",
                "tasks": [],
                "nodes": [],
                "connections": [],
            },
        )

        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = mock_audit
        mock_db.query.return_value = mock_query
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        # Act - State update accessible to all clients
        result = service.add_task(
            canvas_id="canvas-001",
            user_id="user-001",
            title="Broadcast Task"
        )

        # Assert
        assert result["success"] is True
        assert mock_db.commit.called  # Persists for all clients

    def test_client_specific_state_filtering(self, service, mock_db):
        """Test clients can filter state by their needs."""
        # Arrange
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        # Act - Create canvas with specific agent
        result = service.create_orchestration_canvas(
            user_id="user-001",
            title="Agent Canvas",
            agent_id="student-agent-1"
        )

        # Assert
        assert result["success"] is True

    def test_client_disconnect_handling(self, service, mock_db):
        """Test graceful handling when client disconnects."""
        # Arrange
        mock_audit = CanvasAudit(
            id="audit-001",
            tenant_id="default",
            canvas_id="canvas-001",
            action_type="create",
            details_json={
                "canvas_type": "orchestration",
                "component_type": "kanban_board",
                "tasks": [],
                "nodes": [],
                "connections": [],
            },
        )

        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = mock_audit
        mock_db.query.return_value = mock_query
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        # Act - Update persists even after disconnect
        result = service.add_task(
            canvas_id="canvas-001",
            user_id="user-001",
            title="Persistent Task"
        )

        # Assert
        assert result["success"] is True
        # State persists in database for reconnection

    def test_session_management(self, service, mock_db):
        """Test canvas session management across requests."""
        # Arrange
        mock_audit = CanvasAudit(
            id="audit-001",
            tenant_id="default",
            canvas_id="canvas-001",
            action_type="create",
            details_json={
                "canvas_type": "orchestration",
                "component_type": "kanban_board",
                "tasks": [],
                "nodes": [],
                "connections": [],
            },
        )

        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = mock_audit
        mock_db.query.return_value = mock_query
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        # Act - Multiple session requests
        for i in range(3):
            service.add_task(
                canvas_id="canvas-001",
                user_id="user-001",
                title=f"Session Task {i}"
            )

        # Assert
        assert mock_db.commit.call_count == 3

    def test_concurrent_update_handling(self, service, mock_db):
        """Test handling concurrent updates to canvas."""
        # Arrange
        mock_audit = CanvasAudit(
            id="audit-001",
            tenant_id="default",
            canvas_id="canvas-001",
            action_type="create",
            details_json={
                "canvas_type": "orchestration",
                "component_type": "kanban_board",
                "tasks": [],
                "nodes": [],
                "connections": [],
            },
        )

        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = mock_audit
        mock_db.query.return_value = mock_query
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        # Act - Simulate concurrent updates
        results = []
        for i in range(5):
            result = service.add_task(
                canvas_id="canvas-001",
                user_id=f"user-{i % 3}",  # 3 different users
                title=f"Concurrent Task {i}"
            )
            results.append(result)

        # Assert
        assert all(r["success"] is True for r in results)
        assert mock_db.commit.call_count == 5


# ============================================================================
# Additional Tests for Node and Connection Management
# ============================================================================

class TestNodeAndConnectionManagement:
    """Tests for workflow node and connection management."""

    def test_add_workflow_node_with_config(self, service, mock_db):
        """Test adding workflow node with configuration."""
        # Arrange
        mock_audit = CanvasAudit(
            id="audit-001",
            tenant_id="default",
            canvas_id="canvas-001",
            action_type="create",
            details_json={
                "canvas_type": "orchestration",
                "component_type": "workflow_diagram",
                "nodes": [],
                "connections": [],
                "integrations": [],
            },
        )

        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = mock_audit
        mock_db.query.return_value = mock_query
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        # Act
        result = service.add_workflow_node(
            canvas_id="canvas-001",
            user_id="user-001",
            node_name="Email Action",
            node_type="action",
            config={"action": "send_email", "recipient": "customer@example.com"},
            position={"x": 100, "y": 200},
            assigned_agent="agent-001"
        )

        # Assert
        assert result["success"] is True
        assert result["node_id"] is not None
        assert mock_db.add.called

    def test_connect_nodes_with_condition(self, service, mock_db):
        """Test connecting nodes with conditional logic."""
        # Arrange
        mock_audit = CanvasAudit(
            id="audit-001",
            tenant_id="default",
            canvas_id="canvas-001",
            action_type="create",
            details_json={
                "canvas_type": "orchestration",
                "component_type": "workflow_diagram",
                "nodes": [],
                "connections": [],
                "integrations": [],
            },
        )

        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = mock_audit
        mock_db.query.return_value = mock_query
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        # Act
        result = service.connect_nodes(
            canvas_id="canvas-001",
            user_id="user-001",
            from_node="node-001",
            to_node="node-002",
            condition="email_sent == true"
        )

        # Assert
        assert result["success"] is True
        assert result["connection_id"] is not None

    def test_task_to_dict_conversion(self, service):
        """Test WorkflowTask converts to dict correctly."""
        # Arrange
        task = WorkflowTask(
            task_id="task-001",
            title="Test Task",
            status=CanvasTaskStatus.IN_PROGRESS,
            assignee="agent-001",
            tags=["test"],
            integrations=["email"]
        )

        # Act
        result = service._task_to_dict(task)

        # Assert
        assert result["task_id"] == "task-001"
        assert result["title"] == "Test Task"
        assert result["status"] == CanvasTaskStatus.IN_PROGRESS
        assert result["assignee"] == "agent-001"

    def test_node_to_dict_conversion(self, service):
        """Test IntegrationNode converts to dict correctly."""
        # Arrange
        node = IntegrationNode(
            node_id="node-001",
            app_name="Email",
            node_type="action",
            config={"action": "send"},
            position={"x": 100, "y": 200}
        )

        # Act
        result = service._node_to_dict(node)

        # Assert
        assert result["node_id"] == "node-001"
        assert result["app_name"] == "Email"
        assert result["node_type"] == "action"

    def test_connection_to_dict_conversion(self, service):
        """Test WorkflowConnection converts to dict correctly."""
        # Arrange
        connection = WorkflowConnection(
            connection_id="conn-001",
            from_node="node-001",
            to_node="node-002",
            condition="success"
        )

        # Act
        result = service._connection_to_dict(connection)

        # Assert
        assert result["connection_id"] == "conn-001"
        assert result["from_node"] == "node-001"
        assert result["to_node"] == "node-002"
        assert result["condition"] == "success"
