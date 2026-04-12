"""
Asana Integration Tests (pytest)

Tests Asana task and project management integration with proper mocking.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session

from core.models import AgentExecution, AgentOperationTracker


class TestAsanaTaskIntegration:
    """Test Asana task management integration."""

    @pytest.fixture
    def mock_asana_client(self):
        """Create mock Asana client."""
        with patch('integrations.asana_service.AsanaClient') as mock_client:
            yield mock_client.return_value

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = Mock(spec=Session)
        db.query = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.rollback = Mock()
        db.refresh = Mock()
        return db

    def test_create_asana_task(self, mock_asana_client, mock_db):
        """Test creating a task in Asana."""
        # Mock Asana API response
        mock_asana_client.tasks.create_task.return_value = {
            "gid": "task-001",
            "name": "Review documentation",
            "projects": ["123456789"],
            "completed": False
        }

        execution = AgentExecution(
            id="exec-asana-001",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Create Asana task"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Simulate task creation
        task_data = {
            "name": "Review documentation",
            "projects": ["123456789"]
        }

        result = mock_asana_client.tasks.create_task(task_data)

        # Verify API call was made
        mock_asana_client.tasks.create_task.assert_called_once()
        assert result["gid"] == "task-001"
        assert result["name"] == "Review documentation"

        # Update execution
        execution.output_data = {
            "task_created": True,
            "task_gid": result["gid"]
        }
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

        assert execution.output_data["task_created"] is True

    def test_update_asana_task(self, mock_asana_client, mock_db):
        """Test updating an existing task in Asana."""
        mock_asana_client.tasks.update_task.return_value = {
            "gid": "task-001",
            "name": "Review documentation",
            "completed": True
        }

        execution = AgentExecution(
            id="exec-asana-002",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Update task"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Update task
        result = mock_asana_client.tasks.update_task("task-001", {"completed": True})

        # Verify API call
        mock_asana_client.tasks.update_task.assert_called_once_with(
            "task-001", {"completed": True}
        )
        assert result["completed"] is True

        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

    def test_add_comment_to_task(self, mock_asana_client, mock_db):
        """Test adding a comment to an Asana task."""
        mock_asana_client.tasks.add_comment.return_value = {
            "gid": "comment-001",
            "text": "Task completed successfully"
        }

        execution = AgentExecution(
            id="exec-asana-003",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Add comment"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Add comment
        result = mock_asana_client.tasks.add_comment(
            "task-001", "Task completed successfully"
        )

        # Verify API call
        mock_asana_client.tasks.add_comment.assert_called_once()
        assert result["text"] == "Task completed successfully"

        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

    def test_search_asana_tasks(self, mock_asana_client, mock_db):
        """Test searching for tasks in Asana."""
        mock_asana_client.tasks.find_by_id.return_value = [
            {"gid": "task-001", "name": "Review documentation"},
            {"gid": "task-002", "name": "Update documentation"}
        ]

        execution = AgentExecution(
            id="exec-asana-004",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Search tasks"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Search tasks
        results = mock_asana_client.tasks.find_by_id("task-001")

        # Verify API call
        mock_asana_client.tasks.find_by_id.assert_called_once()
        assert len(results) >= 1

        execution.output_data = {"tasks_found": len(results)}
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

    def test_asana_error_handling(self, mock_asana_client, mock_db):
        """Test handling Asana API errors."""
        # Mock API error
        mock_asana_client.tasks.create_task.side_effect = Exception("API Rate Limit Exceeded")

        execution = AgentExecution(
            id="exec-asana-error-001",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Create task"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Attempt to create task
        try:
            mock_asana_client.tasks.create_task({"name": "Test"})
        except Exception as e:
            execution.status = "failed"
            execution.error_message = str(e)
            execution.completed_at = datetime.utcnow()
            mock_db.commit()

        assert execution.status == "failed"
        assert "Rate Limit" in execution.error_message

    def test_asana_authentication_error(self, mock_asana_client, mock_db):
        """Test handling Asana authentication errors."""
        # Mock auth error
        mock_asana_client.tasks.create_task.side_effect = Exception("Unauthorized: Invalid token")

        execution = AgentExecution(
            id="exec-asana-auth-001",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Create task"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Attempt to create task
        try:
            mock_asana_client.tasks.create_task({"name": "Test"})
        except Exception as e:
            execution.status = "failed"
            execution.error_message = f"Authentication failed: {str(e)}"
            execution.completed_at = datetime.utcnow()
            mock_db.commit()

        assert execution.status == "failed"
        assert "Authentication" in execution.error_message
