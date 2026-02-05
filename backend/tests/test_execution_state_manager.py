"""
Tests for Execution State Manager

Tests the ExecutionStateManager after migration from database_manager to
SQLAlchemy async ORM.
"""

import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.execution_state_manager import ExecutionStateManager, get_state_manager
from core.models import WorkflowExecution, WorkflowExecutionStatus
from core.database import get_async_db_session
from sqlalchemy import select


class TestExecutionStateManager:
    """Test ExecutionStateManager functionality"""

    @pytest.mark.asyncio
    async def test_create_execution(self):
        """Test creating a new workflow execution"""
        manager = ExecutionStateManager()

        workflow_id = "test-workflow-123"
        input_data = {"param1": "value1", "param2": "value2"}

        execution_id = await manager.create_execution(workflow_id, input_data)

        assert execution_id is not None
        assert isinstance(execution_id, str)

        # Verify execution was created in database
        async with get_async_db_session() as db:
            result = await db.execute(
                select(WorkflowExecution).where(
                    WorkflowExecution.execution_id == execution_id
                )
            )
            execution = result.scalar_one_or_none()

            assert execution is not None
            assert execution.workflow_id == workflow_id
            assert execution.status == WorkflowExecutionStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_get_execution_state(self):
        """Test retrieving execution state"""
        manager = ExecutionStateManager()

        # First create an execution
        workflow_id = "test-workflow-456"
        input_data = {"test": "data"}
        execution_id = await manager.create_execution(workflow_id, input_data)

        # Now retrieve it
        state = await manager.get_execution_state(execution_id)

        assert state is not None
        assert state["execution_id"] == execution_id
        assert state["workflow_id"] == workflow_id
        assert state["input_data"] == input_data
        assert state["status"] == "pending"

    @pytest.mark.asyncio
    async def test_update_step_status(self):
        """Test updating step status"""
        manager = ExecutionStateManager()

        # Create execution
        execution_id = await manager.create_execution("test-workflow", {})

        # Update step status
        await manager.update_step_status(
            execution_id=execution_id,
            step_id="step_1",
            status="running",
            output={"result": "success"}
        )

        # Verify update
        state = await manager.get_execution_state(execution_id)
        assert state is not None
        assert state["status"] == "pending"  # Still pending overall

    @pytest.mark.asyncio
    async def test_update_execution_status(self):
        """Test updating overall execution status"""
        manager = ExecutionStateManager()

        # Create execution
        execution_id = await manager.create_execution("test-workflow", {})

        # Update status to completed
        await manager.update_execution_status(execution_id, "completed")

        # Verify update
        state = await manager.get_execution_state(execution_id)
        assert state is not None
        assert state["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_step_output(self):
        """Test getting step output"""
        manager = ExecutionStateManager()

        # Create execution
        execution_id = await manager.create_execution("test-workflow", {})

        # Update step with output
        await manager.update_step_status(
            execution_id=execution_id,
            step_id="step_1",
            status="completed",
            output={"data": "test"}
        )

        # Get step output
        output = await manager.get_step_output(execution_id, "step_1")

        assert output == {"data": "test"}

    @pytest.mark.asyncio
    async def test_update_execution_inputs(self):
        """Test updating execution inputs"""
        manager = ExecutionStateManager()

        # Create execution
        execution_id = await manager.create_execution("test-workflow", {"old": "data"})

        # Update inputs
        new_inputs = {"new": "value", "additional": "info"}
        await manager.update_execution_inputs(execution_id, new_inputs)

        # Verify update
        state = await manager.get_execution_state(execution_id)
        assert state is not None
        assert "new" in state["input_data"]
        assert "additional" in state["input_data"]
        assert "old" in state["input_data"]


class TestExecutionStateManagerSingleton:
    """Test the get_state_manager singleton pattern"""

    def test_get_state_manager_returns_singleton(self):
        """Test that get_state_manager returns the same instance"""
        manager1 = get_state_manager()
        manager2 = get_state_manager()

        assert manager1 is manager2  # Same object reference

    def test_get_state_manager_returns_manager_instance(self):
        """Test that get_state_manager returns ExecutionStateManager instance"""
        manager = get_state_manager()

        assert isinstance(manager, ExecutionStateManager)


class TestMigratedFromDatabaseManager:
    """Verify that execution state manager has been migrated from database_manager"""

    def test_no_database_manager_imports(self):
        """Test that execution_state_manager doesn't import database_manager"""
        import core.execution_state_manager as module

        # Read the source file
        source = Path(module.__file__).read_text()

        # Should not contain database_manager imports
        assert "from core.database_manager import" not in source
        assert "import database_manager" not in source

    def test_uses_get_async_db_session(self):
        """Test that manager uses get_async_db_session"""
        import core.execution_state_manager as module

        # Read the source file
        source = Path(module.__file__).read_text()

        # Should use get_async_db_session
        assert "get_async_db_session" in source

    def test_uses_sqlalchemy_orm(self):
        """Test that manager uses SQLAlchemy ORM instead of raw SQL"""
        import core.execution_state_manager as module

        # Read the source file
        source = Path(module.__file__).read_text()

        # Should use select() from sqlalchemy
        assert "from sqlalchemy import select" in source or "sqlalchemy.select" in source

        # Should have WorkflowExecution model usage
        assert "WorkflowExecution" in source


@pytest.mark.parametrize("workflow_id,input_data,step_id,status,output", [
    ("wf1", {"key": "value"}, "step1", "running", {"result": "success"}),
    ("wf2", {"data": "test"}, "step2", "completed", {"done": True}),
])
class TestExecutionStateManagerWithVariousInputs:
    """Test execution state manager with different input scenarios"""

    @pytest.mark.asyncio
    async def test_execution_lifecycle(self, client):
        """Test complete execution lifecycle from creation to completion"""
        manager = ExecutionStateManager()

        # Create
        execution_id = await manager.create_execution("lifecycle-test", {})

        # Initial state should be pending
        state = await manager.get_execution_state(execution_id)
        assert state["status"] == "pending"

        # Update to running
        await manager.update_execution_status(execution_id, "running")

        # Verify
        state = await manager.get_execution_state(execution_id)
        assert state["status"] == "running"

        # Update to completed
        await manager.update_execution_status(execution_id, "completed")

        # Verify
        state = await manager.get_execution_state(execution_id)
        assert state["status"] == "completed"
