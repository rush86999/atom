"""
Tests for API schemas (messaging_schemas, request/response models)

Tests Pydantic request/response schemas for validation, serialization,
and field validation.
"""

import sys
import os
import uuid
import datetime
from typing import Dict, Any

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

from pydantic import ValidationError
from core.messaging_schemas import (
    TaskRequest,
    TaskResult,
    AgentMessage
)


class TestMessagingSchemas:
    """Test AgentMessage and Task schemas for inter-agent communication"""

    def test_valid_agent_message(self):
        """Test accept valid message structure"""
        message = AgentMessage(
            source_agent="agent_1",
            target_agent="agent_2",
            message_type="request",
            payload={"data": "test"},
            context_id="ctx_123"
        )

        assert message.source_agent == "agent_1"
        assert message.target_agent == "agent_2"
        assert message.message_type == "request"
        assert message.payload == {"data": "test"}
        assert message.context_id == "ctx_123"
        assert message.message_id is not None  # Auto-generated UUID
        print("✓ test_valid_agent_message")

    def test_agent_message_serialization(self):
        """Test correct JSON serialization for WebSocket messages"""
        message = AgentMessage(
            source_agent="agent_1",
            target_agent="agent_2",
            message_type="response",
            payload={"result": "success"},
            context_id="ctx_123"
        )

        serialized = message.model_dump()

        assert serialized["source_agent"] == "agent_1"
        assert serialized["target_agent"] == "agent_2"
        assert serialized["message_type"] == "response"
        assert serialized["payload"] == {"result": "success"}
        assert "message_id" in serialized
        print("✓ test_agent_message_serialization")

    def test_agent_message_auto_generates_message_id(self):
        """Test message_id is auto-generated UUID"""
        message1 = AgentMessage(
            source_agent="agent_1",
            target_agent="agent_2",
            message_type="request",
            payload={},
            context_id="ctx_1"
        )

        message2 = AgentMessage(
            source_agent="agent_1",
            target_agent="agent_2",
            message_type="request",
            payload={},
            context_id="ctx_2"
        )

        # Each message should have unique UUID
        assert message1.message_id != message2.message_id
        print("✓ test_agent_message_auto_generates_message_id")


class TestTaskRequest:
    """Test TaskRequest schema for agent task execution"""

    def test_valid_task_request(self):
        """Test accept valid task request"""
        task = TaskRequest(
            user_id="user_123",
            intent="process_data",
            input_data={"file": "data.csv"}
        )

        assert task.user_id == "user_123"
        assert task.intent == "process_data"
        assert task.input_data == {"file": "data.csv"}
        assert task.priority == "medium"  # Default value
        assert task.task_id is not None  # Auto-generated
        assert task.timestamp is not None  # Auto-generated
        print("✓ test_valid_task_request")

    def test_task_request_all_priorities(self):
        """Test all valid priority levels"""
        for priority in ["low", "medium", "high", "critical"]:
            task = TaskRequest(
                user_id="user_123",
                intent="test",
                input_data={},
                priority=priority
            )
            assert task.priority == priority
        print("✓ test_task_request_all_priorities")

    def test_task_request_user_id_validation(self):
        """Test user_id must not be empty"""
        try:
            TaskRequest(
                user_id="",  # Empty user_id
                intent="test",
                input_data={}
            )
            assert False, "Should have raised ValidationError"
        except ValidationError:
            pass  # Expected
        print("✓ test_task_request_user_id_validation")

    def test_task_request_user_id_whitespace_only(self):
        """Test user_id with only whitespace is rejected"""
        try:
            TaskRequest(
                user_id="   ",  # Whitespace only
                intent="test",
                input_data={}
            )
            assert False, "Should have raised ValidationError"
        except ValidationError:
            pass  # Expected
        print("✓ test_task_request_user_id_whitespace_only")

    def test_task_request_serialization(self):
        """Test TaskRequest serializes correctly"""
        task = TaskRequest(
            user_id="user_123",
            intent="analyze",
            input_data={"text": "hello"}
        )

        serialized = task.model_dump()

        assert serialized["user_id"] == "user_123"
        assert serialized["intent"] == "analyze"
        assert serialized["input_data"] == {"text": "hello"}
        assert "timestamp" in serialized
        print("✓ test_task_request_serialization")


class TestTaskResult:
    """Test TaskResult schema for agent execution results"""

    def test_valid_task_result_success(self):
        """Test accept successful task result"""
        result = TaskResult(
            task_id="task_123",
            status="success",
            output_data={"result": 42},
            execution_time_ms=150.5
        )

        assert result.task_id == "task_123"
        assert result.status == "success"
        assert result.output_data == {"result": 42}
        assert result.execution_time_ms == 150.5
        assert result.error_message is None
        assert result.timestamp is not None
        print("✓ test_valid_task_result_success")

    def test_valid_task_result_failure(self):
        """Test accept failed task result with error message"""
        result = TaskResult(
            task_id="task_456",
            status="failure",
            output_data={},
            error_message="Connection timeout",
            execution_time_ms=5000.0
        )

        assert result.status == "failure"
        assert result.error_message == "Connection timeout"
        print("✓ test_valid_task_result_failure")

    def test_task_result_all_statuses(self):
        """Test all valid status values"""
        for status in ["success", "failure", "retry"]:
            result = TaskResult(
                task_id="test_task",
                status=status,
                output_data={},
                execution_time_ms=100.0
            )
            assert result.status == status
        print("✓ test_task_result_all_statuses")

    def test_task_result_serialization(self):
        """Test TaskResult serializes correctly"""
        result = TaskResult(
            task_id="task_789",
            status="success",
            output_data={"answer": "42"},
            execution_time_ms=250.0
        )

        serialized = result.model_dump()

        assert serialized["task_id"] == "task_789"
        assert serialized["status"] == "success"
        assert serialized["output_data"] == {"answer": "42"}
        assert serialized["execution_time_ms"] == 250.0
        assert "timestamp" in serialized
        print("✓ test_task_result_serialization")


class TestSchemaIntegration:
    """Test schema integration and validation pipelines"""

    def test_task_request_to_result_workflow(self):
        """Test end-to-end workflow: TaskRequest -> execution -> TaskResult"""
        # Create task request
        request = TaskRequest(
            user_id="user_123",
            intent="calculate",
            input_data={"x": 10, "y": 20}
        )

        # Simulate execution
        execution_time = 50.0

        # Create task result
        result = TaskResult(
            task_id=request.task_id,
            status="success",
            output_data={"sum": 30},
            execution_time_ms=execution_time
        )

        assert result.task_id == request.task_id
        assert result.status == "success"
        print("✓ test_task_request_to_result_workflow")

    def test_agent_message_context_preservation(self):
        """Test context_id is preserved across message chain"""
        msg1 = AgentMessage(
            source_agent="agent_1",
            target_agent="agent_2",
            message_type="request",
            payload={"action": "start"},
            context_id="workflow_123"
        )

        msg2 = AgentMessage(
            source_agent="agent_2",
            target_agent="agent_1",
            message_type="response",
            payload={"status": "done"},
            context_id="workflow_123"  # Same context
        )

        assert msg1.context_id == msg2.context_id
        print("✓ test_agent_message_context_preservation")


if __name__ == "__main__":
    # Run all tests
    test_classes = [
        TestMessagingSchemas,
        TestTaskRequest,
        TestTaskResult,
        TestSchemaIntegration
    ]

    total_tests = 0
    passed_tests = 0
    failed_tests = []

    for test_class in test_classes:
        instance = test_class()
        test_methods = [m for m in dir(instance) if m.startswith('test_')]

        for method_name in test_methods:
            total_tests += 1
            try:
                method = getattr(instance, method_name)
                method()
                passed_tests += 1
            except Exception as e:
                failed_tests.append(f"{test_class.__name__}.{method_name}: {e}")

    print(f"\n{'='*60}")
    print(f"Tests run: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {len(failed_tests)}")
    if failed_tests:
        print(f"\nFailed tests:")
        for failure in failed_tests:
            print(f"  - {failure}")
        sys.exit(1)
    else:
        print("\n✓ All API schema tests passed!")
        sys.exit(0)
