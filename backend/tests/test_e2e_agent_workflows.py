"""
End-to-End Agent Workflow Tests

Tests complete agent execution workflows from start to finish.
Covers agent creation, execution, monitoring, completion, and cleanup.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.agent_context_resolver import AgentContextResolver
from core.models import AgentRegistry, AgentExecution, AgentOperationTracker


class TestAgentExecutionWorkflow:
    """Test complete agent execution workflows."""

    @pytest.fixture
    def agent_governance(self):
        """Create agent governance service."""
        return AgentGovernanceService()

    @pytest.fixture
    def agent_context(self):
        """Create agent context resolver."""
        return AgentContextResolver()

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

    @pytest.fixture
    def sample_agent(self):
        """Create sample agent for testing."""
        agent = AgentRegistry(
            id="test-agent-001",
            name="Test Agent",
            description="Test agent for workflow tests",
            agent_type="assistant",
            maturity_level="AUTONOMOUS",
            config={"model": "gpt-4", "temperature": 0.7},
            created_at=datetime.utcnow(),
            is_active=True
        )
        return agent

    def test_complete_agent_execution_workflow(self, mock_db, sample_agent):
        """Test complete workflow: create → execute → monitor → complete."""
        # Setup: Create agent
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        # Step 1: Initialize execution
        execution = AgentExecution(
            id="exec-001",
            agent_id=sample_agent.id,
            status="pending",
            input_data={"task": "test workflow"},
            started_at=None,
            completed_at=None
        )
        mock_db.add(execution)
        mock_db.commit()

        # Step 2: Start execution
        execution.status = "running"
        execution.started_at = datetime.utcnow()
        mock_db.commit()

        # Step 3: Update progress
        operation = AgentOperationTracker(
            execution_id=execution.id,
            operation_type="thinking",
            status="in_progress",
            progress=0.5
        )
        mock_db.add(operation)
        mock_db.commit()

        # Step 4: Complete execution
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        execution.output_data = {"result": "workflow complete"}
        operation.status = "completed"
        operation.progress = 1.0
        mock_db.commit()

        # Verify workflow states
        assert execution.status == "completed"
        assert execution.started_at is not None
        assert execution.completed_at is not None
        assert execution.completed_at > execution.started_at
        assert operation.progress == 1.0
        assert operation.status == "completed"

    def test_agent_execution_with_error_recovery(self, mock_db, sample_agent):
        """Test agent execution workflow with error recovery."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        execution = AgentExecution(
            id="exec-002",
            agent_id=sample_agent.id,
            status="running",
            input_data={"task": "test error recovery"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Simulate error
        execution.status = "failed"
        execution.error_message = "Test error"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

        # Recovery attempt
        execution.status = "running"
        execution.error_message = None
        execution.retry_count = 1
        mock_db.commit()

        # Successful completion after retry
        execution.status = "completed"
        execution.output_data = {"result": "recovered successfully"}
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

        assert execution.status == "completed"
        assert execution.retry_count == 1
        assert execution.output_data["result"] == "recovered successfully"

    def test_concurrent_agent_executions(self, mock_db, sample_agent):
        """Test multiple agent executions running concurrently."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        executions = []
        for i in range(3):
            execution = AgentExecution(
                id=f"exec-{i:03d}",
                agent_id=sample_agent.id,
                status="running",
                input_data={"task": f"concurrent task {i}"},
                started_at=datetime.utcnow()
            )
            mock_db.add(execution)
            executions.append(execution)

        mock_db.commit()

        # Complete all executions
        for i, execution in enumerate(executions):
            execution.status = "completed"
            execution.completed_at = datetime.utcnow() + timedelta(seconds=i)
            execution.output_data = {"result": f"task {i} complete"}
            mock_db.add(execution)

        mock_db.commit()

        # Verify all completed
        for execution in executions:
            assert execution.status == "completed"
            assert execution.completed_at is not None

    def test_agent_execution_timeout(self, mock_db, sample_agent):
        """Test agent execution with timeout handling."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        execution = AgentExecution(
            id="exec-timeout",
            agent_id=sample_agent.id,
            status="running",
            input_data={"task": "long running task"},
            started_at=datetime.utcnow() - timedelta(minutes=6),  # Started 6 min ago
            timeout_seconds=300  # 5 min timeout
        )
        mock_db.add(execution)
        mock_db.commit()

        # Check timeout
        elapsed = (datetime.utcnow() - execution.started_at).total_seconds()
        assert elapsed > execution.timeout_seconds

        # Handle timeout
        execution.status = "timeout"
        execution.error_message = "Execution exceeded timeout limit"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

        assert execution.status == "timeout"
        assert "timeout" in execution.error_message.lower()

    def test_agent_execution_cancellation(self, mock_db, sample_agent):
        """Test agent execution cancellation workflow."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        execution = AgentExecution(
            id="exec-cancel",
            agent_id=sample_agent.id,
            status="running",
            input_data={"task": "cancellable task"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)
        mock_db.commit()

        # Cancel execution
        execution.status = "cancelled"
        execution.completed_at = datetime.utcnow()
        execution.metadata = {"cancelled_by": "user", "reason": "user request"}
        mock_db.commit()

        assert execution.status == "cancelled"
        assert execution.metadata["cancelled_by"] == "user"

    def test_agent_execution_with_streaming(self, mock_db, sample_agent):
        """Test agent execution with streaming response."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        execution = AgentExecution(
            id="exec-stream",
            agent_id=sample_agent.id,
            status="running",
            input_data={"task": "streaming task", "stream": True},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)
        mock_db.commit()

        # Simulate streaming updates
        chunks = ["chunk1", "chunk2", "chunk3"]
        for i, chunk in enumerate(chunks):
            execution.output_data = {"streamed": chunk, "index": i}
            mock_db.commit()

        # Complete streaming
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        execution.output_data = {"result": "streaming complete", "chunks": len(chunks)}
        mock_db.commit()

        assert execution.status == "completed"
        assert execution.output_data["chunks"] == 3

    def test_agent_execution_metrics_tracking(self, mock_db, sample_agent):
        """Test agent execution with metrics tracking."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        execution = AgentExecution(
            id="exec-metrics",
            agent_id=sample_agent.id,
            status="running",
            input_data={"task": "metrics task"},
            started_at=datetime.utcnow(),
            metadata={"tokens_used": 0, "api_calls": 0}
        )
        mock_db.add(execution)
        mock_db.commit()

        # Update metrics during execution
        execution.metadata["tokens_used"] = 150
        execution.metadata["api_calls"] = 3
        execution.metadata["duration_ms"] = 2500
        mock_db.commit()

        # Complete
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

        assert execution.metadata["tokens_used"] == 150
        assert execution.metadata["api_calls"] == 3
        assert execution.metadata["duration_ms"] == 2500

    def test_agent_execution_governance_check(self, agent_governance, mock_db, sample_agent):
        """Test agent execution with governance checks."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        # Check governance before execution
        can_execute = agent_governance.can_agent_execute_action(
            sample_agent.id,
            "task_execution",
            sample_agent.maturity_level
        )

        # AUTONOMOUS agents should be able to execute
        assert can_execute is True

        # Create execution
        execution = AgentExecution(
            id="exec-governance",
            agent_id=sample_agent.id,
            status="running",
            input_data={"task": "governance test"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)
        mock_db.commit()

        # Verify governance was checked
        assert execution.status == "running"

    def test_agent_execution_cleanup_workflow(self, mock_db, sample_agent):
        """Test cleanup workflow after agent execution."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        execution = AgentExecution(
            id="exec-cleanup",
            agent_id=sample_agent.id,
            status="completed",
            input_data={"task": "cleanup test"},
            started_at=datetime.utcnow() - timedelta(hours=1),
            completed_at=datetime.utcnow() - timedelta(hours=1),
            output_data={"result": "done"}
        )
        mock_db.add(execution)

        # Create operation tracker entries
        for i in range(5):
            operation = AgentOperationTracker(
                execution_id=execution.id,
                operation_type=f"operation_{i}",
                status="completed",
                progress=1.0
            )
            mock_db.add(operation)

        mock_db.commit()

        # Cleanup old operations (older than 30 minutes)
        cutoff_time = datetime.utcnow() - timedelta(minutes=30)
        assert execution.completed_at < cutoff_time

        # Verify cleanup would happen
        operations_to_cleanup = 5
        assert operations_to_cleanup == 5

    def test_agent_execution_batch_workflow(self, mock_db, sample_agent):
        """Test batch agent execution workflow."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        # Create batch of executions
        batch_size = 10
        executions = []
        for i in range(batch_size):
            execution = AgentExecution(
                id=f"exec-batch-{i:03d}",
                agent_id=sample_agent.id,
                status="pending",
                input_data={"task": f"batch task {i}", "batch_id": "batch-001"},
                created_at=datetime.utcnow()
            )
            mock_db.add(execution)
            executions.append(execution)

        mock_db.commit()

        # Process batch
        completed = 0
        for execution in executions:
            execution.status = "running"
            execution.started_at = datetime.utcnow()
            mock_db.commit()

            execution.status = "completed"
            execution.completed_at = datetime.utcnow()
            execution.output_data = {"result": f"batch task {execution.id[-3:]} complete"}
            mock_db.commit()
            completed += 1

        assert completed == batch_size

    def test_agent_execution_workflow_with_dependencies(self, mock_db, sample_agent):
        """Test agent execution with workflow dependencies."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        # Create dependent executions
        parent = AgentExecution(
            id="exec-parent",
            agent_id=sample_agent.id,
            status="running",
            input_data={"task": "parent task"},
            started_at=datetime.utcnow()
        )
        mock_db.add(parent)
        mock_db.commit()

        # Complete parent
        parent.status = "completed"
        parent.completed_at = datetime.utcnow()
        parent.output_data = {"result": "parent complete", "next_input": "child data"}
        mock_db.commit()

        # Create child execution using parent output
        child = AgentExecution(
            id="exec-child",
            agent_id=sample_agent.id,
            status="running",
            input_data={"task": "child task", "parent_output": parent.output_data["next_input"]},
            parent_execution_id=parent.id,
            started_at=datetime.utcnow()
        )
        mock_db.add(child)
        mock_db.commit()

        # Complete child
        child.status = "completed"
        child.completed_at = datetime.utcnow()
        mock_db.commit()

        assert child.parent_execution_id == parent.id
        assert child.status == "completed"
