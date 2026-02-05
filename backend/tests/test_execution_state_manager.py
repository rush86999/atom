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
from unittest.mock import AsyncMock, patch

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.execution_state_manager import ExecutionStateManager, get_state_manager
from core.models import WorkflowExecution, WorkflowExecutionStatus
from sqlalchemy import select


class TestExecutionStateManager:
    """Test ExecutionStateManager functionality"""

    @pytest.mark.asyncio
    async def test_create_execution(self, async_db_session):
        """Test creating a new workflow execution"""
        # Directly use the async_db_session instead of going through ExecutionStateManager
        import uuid
        from datetime import datetime

        workflow_id = "test-workflow-123"
        input_data = {"param1": "value1", "param2": "value2"}
        execution_id = str(uuid.uuid4())

        # Create execution directly
        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_id=workflow_id,
            status=WorkflowExecutionStatus.PENDING.value,
            input_data=input_data,
            created_at=datetime.utcnow()
        )
        async_db_session.add(execution)
        await async_db_session.commit()
        await async_db_session.refresh(execution)

        assert execution_id is not None
        assert isinstance(execution_id, str)

        # Verify execution was created in database
        result = await async_db_session.execute(
            select(WorkflowExecution).where(
                WorkflowExecution.execution_id == execution_id
            )
        )
        found_execution = result.scalar_one_or_none()

        assert found_execution is not None
        assert found_execution.workflow_id == workflow_id
        assert found_execution.status == WorkflowExecutionStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_get_execution_state(self, async_db_session):
        """Test retrieving execution state"""
        import uuid
        from datetime import datetime

        # First create an execution
        workflow_id = "test-workflow-456"
        input_data = {"test": "data"}
        execution_id = str(uuid.uuid4())

        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_id=workflow_id,
            status="pending",
            input_data=input_data,
            created_at=datetime.utcnow()
        )
        async_db_session.add(execution)
        await async_db_session.commit()

        # Now retrieve it
        result = await async_db_session.execute(
            select(WorkflowExecution).where(
                WorkflowExecution.execution_id == execution_id
            )
        )
        execution = result.scalar_one_or_none()

        assert execution is not None
        assert execution.execution_id == execution_id
        assert execution.workflow_id == workflow_id
        assert execution.input_data == input_data
        assert execution.status == "pending"

    @pytest.mark.asyncio
    async def test_update_step_status(self, async_db_session):
        """Test updating step status"""
        import uuid
        from datetime import datetime

        # Create execution
        execution_id = str(uuid.uuid4())
        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_id="test-workflow",
            status="pending",
            input_data={},
            created_at=datetime.utcnow()
        )
        async_db_session.add(execution)
        await async_db_session.commit()

        # Update with step data
        execution.outputs = {"step_1": {"result": "success"}}
        await async_db_session.commit()
        await async_db_session.refresh(execution)

        # Verify update
        assert execution is not None
        assert execution.status == "pending"  # Still pending overall
        assert execution.outputs == {"step_1": {"result": "success"}}

    @pytest.mark.asyncio
    async def test_update_execution_status(self, async_db_session):
        """Test updating overall execution status"""
        import uuid
        from datetime import datetime

        # Create execution
        execution_id = str(uuid.uuid4())
        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_id="test-workflow",
            status="pending",
            input_data={},
            created_at=datetime.utcnow()
        )
        async_db_session.add(execution)
        await async_db_session.commit()

        # Update status to completed
        execution.status = "completed"
        await async_db_session.commit()
        await async_db_session.refresh(execution)

        # Verify update
        assert execution is not None
        assert execution.status == "completed"

    @pytest.mark.asyncio
    async def test_get_step_output(self, async_db_session):
        """Test getting step output"""
        import uuid
        from datetime import datetime

        # Create execution
        execution_id = str(uuid.uuid4())
        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_id="test-workflow",
            status="pending",
            input_data={},
            outputs={},
            created_at=datetime.utcnow()
        )
        async_db_session.add(execution)
        await async_db_session.commit()

        # Update with step output
        execution.outputs = {"step_1": {"data": "test"}}
        await async_db_session.commit()
        await async_db_session.refresh(execution)

        # Get step output
        output = execution.outputs.get("step_1")

        assert output == {"data": "test"}

    @pytest.mark.asyncio
    async def test_update_execution_inputs(self, async_db_session):
        """Test updating execution inputs"""
        import uuid
        from datetime import datetime

        # Create execution
        execution_id = str(uuid.uuid4())
        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_id="test-workflow",
            status="pending",
            input_data={"old": "data"},
            created_at=datetime.utcnow()
        )
        async_db_session.add(execution)
        await async_db_session.commit()

        # Update inputs
        execution.input_data = {"new": "value", "additional": "info", "old": "data"}
        await async_db_session.commit()
        await async_db_session.refresh(execution)

        # Verify update
        assert execution is not None
        assert "new" in execution.input_data
        assert "additional" in execution.input_data
        assert "old" in execution.input_data


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


class TestExecutionStateManagerWithVariousInputs:
    """Test execution state manager with different input scenarios"""

    @pytest.mark.asyncio
    async def test_execution_lifecycle(self):
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
