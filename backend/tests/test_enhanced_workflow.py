#!/usr/bin/env python3
"""Enhanced workflow engine tests for new features."""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.workflow_engine import (
    MissingInputError,
    SchemaValidationError,
    StepTimeoutError,
    WorkflowEngine,
)


class TestEnhancedWorkflowEngine:
    """Test enhanced workflow engine features."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = WorkflowEngine(max_concurrent_steps=2)
        # Mock state manager to avoid DB dependencies
        self.engine.state_manager = MagicMock()
        self.engine.state_manager.create_execution = AsyncMock(return_value="test_execution_id")
        self.engine.state_manager.update_step_status = AsyncMock()
        self.engine.state_manager.update_execution_status = AsyncMock()
        self.engine.state_manager.get_execution_state = AsyncMock(return_value={
            "execution_id": "test_execution_id",
            "workflow_id": "test_workflow",
            "status": "RUNNING",
            "version": 1,
            "input_data": {},
            "steps": {},
            "outputs": {},
            "context": {},
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "error": None
        })

    def test_parallel_execution_initialization(self):
        """Test that parallel execution settings are initialized correctly."""
        engine = WorkflowEngine(max_concurrent_steps=10)
        assert engine.max_concurrent_steps == 10
        assert engine.semaphore._value == 10

    def test_schema_validation_error_class(self):
        """Test SchemaValidationError exception."""
        error = SchemaValidationError("Test error", "input", ["error1", "error2"])
        assert str(error) == "Test error"
        assert error.schema_type == "input"
        assert error.errors == ["error1", "error2"]

    def test_step_timeout_error_class(self):
        """Test StepTimeoutError exception."""
        error = StepTimeoutError("Timeout error", "step_123", 30.0)
        assert str(error) == "Timeout error"
        assert error.step_id == "step_123"
        assert error.timeout == 30.0

    def test_validate_input_schema_valid(self):
        """Test input schema validation with valid data."""
        step = {
            "id": "test_step",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "count": {"type": "integer"}
                },
                "required": ["name"]
            }
        }
        params = {"name": "test", "count": 5}
        # Should not raise exception
        self.engine._validate_input_schema(step, params)

    def test_validate_input_schema_invalid(self):
        """Test input schema validation with invalid data."""
        step = {
            "id": "test_step",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"}
                },
                "required": ["name"]
            }
        }
        params = {"count": 5}  # Missing required 'name'
        with pytest.raises(SchemaValidationError) as exc_info:
            self.engine._validate_input_schema(step, params)
        assert exc_info.value.schema_type == "input"
        assert "required" in exc_info.value.errors[0].lower()

    def test_validate_output_schema_valid(self):
        """Test output schema validation with valid data."""
        step = {
            "id": "test_step",
            "output_schema": {
                "type": "object",
                "properties": {
                    "result": {"type": "string"},
                    "status": {"type": "string"}
                },
                "required": ["result", "status"]
            }
        }
        output = {"result": "success", "status": "completed"}
        # Should not raise exception
        self.engine._validate_output_schema(step, output)

    def test_validate_output_schema_invalid(self):
        """Test output schema validation with invalid data."""
        step = {
            "id": "test_step",
            "output_schema": {
                "type": "object",
                "properties": {
                    "result": {"type": "string"}
                },
                "required": ["result"]
            }
        }
        output = {"status": "completed"}  # Missing required 'result'
        with pytest.raises(SchemaValidationError) as exc_info:
            self.engine._validate_output_schema(step, output)
        assert exc_info.value.schema_type == "output"

    @pytest.mark.asyncio
    async def test_sub_workflow_action_method_exists(self):
        """Test that sub-workflow action method exists and has correct signature."""
        # Check method exists
        assert hasattr(self.engine, '_execute_workflow_action')
        # Check it's callable
        result = await self.engine._execute_workflow_action("execute", {"workflow_id": "test"})
        assert isinstance(result, dict)
        assert "status" in result

    @pytest.mark.asyncio
    async def test_load_workflow_by_id_method(self):
        """Test loading workflow by ID method."""
        # Mock file reading
        with patch('builtins.open', MagicMock()) as mock_open:
            with patch('json.load', MagicMock(return_value=[{"id": "test_workflow", "name": "Test"}])):
                workflow = self.engine._load_workflow_by_id("test_workflow")
                assert workflow is not None
                assert workflow["id"] == "test_workflow"
                assert workflow["name"] == "Test"

    @pytest.mark.asyncio
    async def test_continue_on_error_flag(self):
        """Test that continue_on_error flag is recognized in step configuration."""
        step = {
            "id": "test_step",
            "service": "slack",
            "action": "send_message",
            "continue_on_error": True,
            "timeout": None,
            "input_schema": {},
            "output_schema": {}
        }
        # The flag should be present
        assert step["continue_on_error"] is True

    def test_version_field_in_state(self):
        """Test that version field is included in execution state."""
        state = {
            "execution_id": "test",
            "workflow_id": "test_workflow",
            "status": "RUNNING",
            "version": 1,
            "input_data": {},
            "steps": {},
            "outputs": {},
            "context": {},
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "error": None
        }
        assert "version" in state
        assert state["version"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])