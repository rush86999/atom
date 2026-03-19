"""
Unit Tests for Messaging Schemas

Tests message schema definitions and validation:
- TaskRequest schema (task requests to agents)
- TaskResult schema (task results from agents)
- AgentMessage schema (inter-agent communication)
- Field validation (user_id, priority, status)
- Timestamp generation
- UUID generation

Target Coverage: 95%
Target Branch Coverage: 60%+
"""

import pytest
from datetime import datetime
from pydantic import ValidationError
from unittest.mock import Mock, patch
import uuid
import json

from core.messaging_schemas import (
    TaskRequest,
    TaskResult,
    AgentMessage
)


class TestTaskRequest:
    """Tests for TaskRequest schema."""

    def test_create_task_request_minimal(self):
        """Test creating TaskRequest with minimal required fields."""
        # Arrange: Task request data
        task_data = {
            "user_id": "user-123",
            "intent": "summarize this text",
            "input_data": {"text": "Hello World"}
        }

        # Act: Create task request
        task = TaskRequest(**task_data)

        # Assert: Verify fields
        assert task.user_id == "user-123"
        assert task.intent == "summarize this text"
        assert task.input_data == {"text": "Hello World"}
        assert task.priority == "medium"  # Default
        assert isinstance(task.task_id, str)
        assert isinstance(task.timestamp, datetime)

    def test_create_task_request_with_all_fields(self):
        """Test creating TaskRequest with all fields specified."""
        # Arrange: Task request data with all fields
        fixed_uuid = str(uuid.uuid4())
        fixed_timestamp = datetime.utcnow()

        task_data = {
            "task_id": fixed_uuid,
            "user_id": "user-456",
            "intent": "analyze data",
            "input_data": {"data": [1, 2, 3]},
            "priority": "high",
            "timestamp": fixed_timestamp
        }

        # Act: Create task request
        task = TaskRequest(**task_data)

        # Assert: Verify all fields
        assert task.task_id == fixed_uuid
        assert task.user_id == "user-456"
        assert task.intent == "analyze data"
        assert task.input_data == {"data": [1, 2, 3]}
        assert task.priority == "high"
        assert task.timestamp == fixed_timestamp

    def test_task_request_default_task_id_is_uuid(self):
        """Test TaskRequest generates UUID for task_id by default."""
        # Arrange & Act: Create task without task_id
        task = TaskRequest(
            user_id="user-123",
            intent="test",
            input_data={}
        )

        # Assert: UUID generated
        assert isinstance(task.task_id, str)
        # Verify it's a valid UUID
        uuid.UUID(task.task_id)  # Will raise if invalid

    def test_task_request_default_timestamp_is_now(self):
        """Test TaskRequest generates current timestamp by default."""
        # Arrange: Get time before creation
        before = datetime.utcnow()

        # Act: Create task without timestamp
        task = TaskRequest(
            user_id="user-123",
            intent="test",
            input_data={}
        )

        # Arrange: Get time after creation
        after = datetime.utcnow()

        # Assert: Timestamp is within time window
        assert before <= task.timestamp <= after

    def test_task_request_priority_low(self):
        """Test TaskRequest with low priority."""
        task = TaskRequest(
            user_id="user-123",
            intent="test",
            input_data={},
            priority="low"
        )

        assert task.priority == "low"

    def test_task_request_priority_medium(self):
        """Test TaskRequest with medium priority."""
        task = TaskRequest(
            user_id="user-123",
            intent="test",
            input_data={},
            priority="medium"
        )

        assert task.priority == "medium"

    def test_task_request_priority_high(self):
        """Test TaskRequest with high priority."""
        task = TaskRequest(
            user_id="user-123",
            intent="test",
            input_data={},
            priority="high"
        )

        assert task.priority == "high"

    def test_task_request_priority_critical(self):
        """Test TaskRequest with critical priority."""
        task = TaskRequest(
            user_id="user-123",
            intent="test",
            input_data={},
            priority="critical"
        )

        assert task.priority == "critical"

    def test_task_request_invalid_priority(self):
        """Test TaskRequest rejects invalid priority."""
        # Arrange: Task data with invalid priority
        task_data = {
            "user_id": "user-123",
            "intent": "test",
            "input_data": {},
            "priority": "urgent"  # Invalid (not in enum)
        }

        # Act/Assert: Should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            TaskRequest(**task_data)

        # Verify error message
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('priority',) for error in errors)

    def test_task_request_empty_user_id_raises_error(self):
        """Test TaskRequest rejects empty user_id."""
        # Arrange: Task data with empty user_id
        task_data = {
            "user_id": "",  # Empty
            "intent": "test",
            "input_data": {}
        }

        # Act/Assert: Should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            TaskRequest(**task_data)

        # Verify error message
        errors = exc_info.value.errors()
        assert any('user_id' in str(error) for error in errors)

    def test_task_request_whitespace_only_user_id_raises_error(self):
        """Test TaskRequest rejects whitespace-only user_id."""
        # Arrange: Task data with whitespace user_id
        task_data = {
            "user_id": "   ",  # Whitespace only
            "intent": "test",
            "input_data": {}
        }

        # Act/Assert: Should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            TaskRequest(**task_data)

        # Verify error message mentions user_id must not be empty
        errors = exc_info.value.errors()
        assert any('user_id' in str(error) for error in errors)

    def test_task_request_missing_user_id_raises_error(self):
        """Test TaskRequest requires user_id field."""
        # Arrange: Task data without user_id
        task_data = {
            "intent": "test",
            "input_data": {}
        }

        # Act/Assert: Should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            TaskRequest(**task_data)

        # Verify user_id is missing
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('user_id',) for error in errors)

    def test_task_request_complex_input_data(self):
        """Test TaskRequest with complex nested input_data."""
        # Arrange: Complex nested data
        complex_data = {
            "text": "Hello",
            "metadata": {
                "source": "email",
                "timestamp": "2026-03-18T10:00:00Z",
                "nested": {
                    "level1": {
                        "level2": [1, 2, 3]
                    }
                }
            },
            "entities": [
                {"type": "person", "name": "John"},
                {"type": "org", "name": "Acme Corp"}
            ]
        }

        # Act: Create task with complex data
        task = TaskRequest(
            user_id="user-123",
            intent="extract entities",
            input_data=complex_data
        )

        # Assert: Complex data preserved
        assert task.input_data == complex_data
        assert task.input_data["metadata"]["nested"]["level1"]["level2"] == [1, 2, 3]

    def test_task_request_empty_input_data(self):
        """Test TaskRequest with empty input_data."""
        task = TaskRequest(
            user_id="user-123",
            intent="test",
            input_data={}
        )

        assert task.input_data == {}

    def test_task_request_serialization(self):
        """Test TaskRequest serializes to JSON correctly."""
        # Arrange: Create task
        fixed_uuid = str(uuid.uuid4())
        fixed_timestamp = datetime.utcnow()

        task = TaskRequest(
            task_id=fixed_uuid,
            user_id="user-123",
            intent="serialize me",
            input_data={"key": "value"},
            priority="high",
            timestamp=fixed_timestamp
        )

        # Act: Serialize to JSON
        json_data = task.model_dump_json()

        # Assert: Verify JSON structure
        data = json.loads(json_data)
        assert data["task_id"] == fixed_uuid
        assert data["user_id"] == "user-123"
        assert data["intent"] == "serialize me"
        assert data["input_data"] == {"key": "value"}
        assert data["priority"] == "high"

    def test_task_request_deserialization(self):
        """Test TaskRequest deserializes from JSON correctly."""
        # Arrange: JSON data
        json_data = {
            "task_id": str(uuid.uuid4()),
            "user_id": "user-123",
            "intent": "deserialize me",
            "input_data": {"key": "value"},
            "priority": "low",
            "timestamp": datetime.utcnow().isoformat()
        }

        # Act: Deserialize from JSON
        task = TaskRequest(**json_data)

        # Assert: Verify task
        assert isinstance(task, TaskRequest)
        assert task.user_id == "user-123"
        assert task.intent == "deserialize me"


class TestTaskResult:
    """Tests for TaskResult schema."""

    def test_create_task_result_success(self):
        """Test creating TaskResult with success status."""
        # Arrange: Task result data
        result_data = {
            "task_id": "task-123",
            "status": "success",
            "output_data": {"summary": "Text summarized"},
            "execution_time_ms": 150.5
        }

        # Act: Create task result
        result = TaskResult(**result_data)

        # Assert: Verify fields
        assert result.task_id == "task-123"
        assert result.status == "success"
        assert result.output_data == {"summary": "Text summarized"}
        assert result.execution_time_ms == 150.5
        assert result.error_message is None  # Default
        assert isinstance(result.timestamp, datetime)

    def test_create_task_result_failure_with_error(self):
        """Test creating TaskResult with failure status and error."""
        result_data = {
            "task_id": "task-456",
            "status": "failure",
            "output_data": {},
            "error_message": "API rate limit exceeded",
            "execution_time_ms": 50.0
        }

        result = TaskResult(**result_data)

        assert result.status == "failure"
        assert result.error_message == "API rate limit exceeded"
        assert result.execution_time_ms == 50.0

    def test_create_task_result_retry_status(self):
        """Test creating TaskResult with retry status."""
        result_data = {
            "task_id": "task-789",
            "status": "retry",
            "output_data": {},
            "error_message": "Temporary network error",
            "execution_time_ms": 100.0
        }

        result = TaskResult(**result_data)

        assert result.status == "retry"
        assert result.error_message == "Temporary network error"

    def test_task_result_invalid_status(self):
        """Test TaskResult rejects invalid status."""
        # Arrange: Invalid status
        result_data = {
            "task_id": "task-123",
            "status": "pending",  # Invalid (not in enum)
            "output_data": {},
            "execution_time_ms": 100.0
        }

        # Act/Assert: Should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            TaskResult(**result_data)

        errors = exc_info.value.errors()
        assert any(error['loc'] == ('status',) for error in errors)

    def test_task_result_execution_time_float(self):
        """Test TaskResult with float execution time."""
        result = TaskResult(
            task_id="task-123",
            status="success",
            output_data={},
            execution_time_ms=123.456
        )

        assert result.execution_time_ms == 123.456

    def test_task_result_execution_time_integer(self):
        """Test TaskResult accepts integer execution time."""
        result = TaskResult(
            task_id="task-123",
            status="success",
            output_data={},
            execution_time_ms=100  # Integer
        )

        assert result.execution_time_ms == 100
        assert isinstance(result.execution_time_ms, float)  # Converted to float

    def test_task_result_with_large_output_data(self):
        """Test TaskResult with large output data."""
        large_output = {
            "results": [{"id": i, "value": f"item-{i}"} for i in range(1000)]
        }

        result = TaskResult(
            task_id="task-123",
            status="success",
            output_data=large_output,
            execution_time_ms=500.0
        )

        assert len(result.output_data["results"]) == 1000

    def test_task_result_serialization(self):
        """Test TaskResult serializes to JSON correctly."""
        result = TaskResult(
            task_id="task-123",
            status="success",
            output_data={"key": "value"},
            execution_time_ms=100.0,
            error_message=None
        )

        # Act: Serialize to JSON
        json_data = result.model_dump_json()

        # Assert: Verify JSON
        data = json.loads(json_data)
        assert data["task_id"] == "task-123"
        assert data["status"] == "success"
        assert data["output_data"] == {"key": "value"}
        assert data["error_message"] is None


class TestAgentMessage:
    """Tests for AgentMessage schema."""

    def test_create_agent_message_minimal(self):
        """Test creating AgentMessage with required fields."""
        # Arrange: Message data
        message_data = {
            "source_agent": "agent-orchestrator",
            "target_agent": "agent-researcher",
            "message_type": "task_request",
            "payload": {"query": "find latest research"},
            "context_id": "ctx-123"
        }

        # Act: Create message
        message = AgentMessage(**message_data)

        # Assert: Verify fields
        assert message.source_agent == "agent-orchestrator"
        assert message.target_agent == "agent-researcher"
        assert message.message_type == "task_request"
        assert message.payload == {"query": "find latest research"}
        assert message.context_id == "ctx-123"
        assert isinstance(message.message_id, str)

    def test_agent_message_default_message_id_is_uuid(self):
        """Test AgentMessage generates UUID by default."""
        message = AgentMessage(
            source_agent="agent-a",
            target_agent="agent-b",
            message_type="greeting",
            payload={"hello": "world"},
            context_id="ctx-456"
        )

        # Assert: UUID generated
        assert isinstance(message.message_id, str)
        uuid.UUID(message.message_id)  # Will raise if invalid

    def test_agent_message_with_custom_message_id(self):
        """Test AgentMessage accepts custom message_id."""
        custom_id = "custom-msg-123"

        message = AgentMessage(
            message_id=custom_id,
            source_agent="agent-a",
            target_agent="agent-b",
            message_type="greeting",
            payload={},
            context_id="ctx-789"
        )

        assert message.message_id == custom_id

    def test_agent_message_complex_payload(self):
        """Test AgentMessage with complex nested payload."""
        complex_payload = {
            "task": {
                "id": "task-123",
                "steps": [
                    {"step": 1, "action": "fetch"},
                    {"step": 2, "action": "process"}
                ],
                "metadata": {
                    "priority": "high",
                    "deadline": "2026-03-19"
                }
            }
        }

        message = AgentMessage(
            source_agent="agent-orchestrator",
            target_agent="agent-worker",
            message_type="task_assignment",
            payload=complex_payload,
            context_id="ctx-complex"
        )

        assert message.payload["task"]["steps"][0]["action"] == "fetch"

    def test_agent_message_empty_payload(self):
        """Test AgentMessage with empty payload."""
        message = AgentMessage(
            source_agent="agent-a",
            target_agent="agent-b",
            message_type="ping",
            payload={},
            context_id="ctx-empty"
        )

        assert message.payload == {}

    def test_agent_message_serialization(self):
        """Test AgentMessage serializes to JSON correctly."""
        message = AgentMessage(
            source_agent="agent-a",
            target_agent="agent-b",
            message_type="data",
            payload={"key": "value"},
            context_id="ctx-serialize"
        )

        # Act: Serialize to JSON
        json_data = message.model_dump_json()

        # Assert: Verify JSON
        data = json.loads(json_data)
        assert data["source_agent"] == "agent-a"
        assert data["target_agent"] == "agent-b"
        assert data["message_type"] == "data"
        assert data["payload"] == {"key": "value"}
        assert data["context_id"] == "ctx-serialize"

    def test_agent_message_context_protection(self):
        """Test AgentMessage enforces context_id (Context Protection)."""
        # Context Protection: Ensure context is passed between agents
        message = AgentMessage(
            source_agent="agent-a",
            target_agent="agent-b",
            message_type="request",
            payload={},
            context_id="conversation-123"  # Required context tracking
        )

        assert message.context_id == "conversation-123"


class TestSchemaValidationEdgeCases:
    """Tests for edge cases in schema validation."""

    def test_task_request_with_unicode(self):
        """Test TaskRequest handles unicode characters."""
        task = TaskRequest(
            user_id="user-世界",
            intent="分析中文文本",
            input_data={"text": "你好世界 🌍"}
        )

        assert "世界" in task.user_id
        assert "中文" in task.intent
        assert "🌍" in task.input_data["text"]

    def test_task_result_with_unicode_error(self):
        """Test TaskResult handles unicode in error messages."""
        result = TaskResult(
            task_id="task-123",
            status="failure",
            output_data={},
            error_message="Error: 错误 🔥",
            execution_time_ms=100.0
        )

        assert "错误" in result.error_message
        assert "🔥" in result.error_message

    def test_agent_message_with_unicode(self):
        """Test AgentMessage handles unicode in payload."""
        message = AgentMessage(
            source_agent="agent-α",
            target_agent="agent-β",
            message_type="data",
            payload={"text": "Hello 世界 🌍"},
            context_id="ctx-unicode"
        )

        assert "α" in message.source_agent
        assert "β" in message.target_agent
        assert "世界" in message.payload["text"]


class TestTimestampGeneration:
    """Tests for automatic timestamp generation."""

    def test_task_result_timestamp_auto_generated(self):
        """Test TaskResult generates timestamp automatically."""
        before = datetime.utcnow()

        result = TaskResult(
            task_id="task-123",
            status="success",
            output_data={},
            execution_time_ms=100.0
        )

        after = datetime.utcnow()

        assert before <= result.timestamp <= after

    def test_task_result_timestamp_custom(self):
        """Test TaskResult accepts custom timestamp."""
        custom_time = datetime(2026, 3, 18, 10, 30, 0)

        result = TaskResult(
            task_id="task-123",
            status="success",
            output_data={},
            execution_time_ms=100.0,
            timestamp=custom_time
        )

        assert result.timestamp == custom_time


class TestMissingRequiredFields:
    """Tests for missing required field validation."""

    def test_task_request_missing_intent(self):
        """Test TaskRequest requires intent field."""
        with pytest.raises(ValidationError) as exc_info:
            TaskRequest(
                user_id="user-123",
                input_data={}
                # Missing: intent
            )

        errors = exc_info.value.errors()
        assert any(error['loc'] == ('intent',) for error in errors)

    def test_task_request_missing_input_data(self):
        """Test TaskRequest requires input_data field."""
        with pytest.raises(ValidationError) as exc_info:
            TaskRequest(
                user_id="user-123",
                intent="test"
                # Missing: input_data
            )

        errors = exc_info.value.errors()
        assert any(error['loc'] == ('input_data',) for error in errors)

    def test_task_result_missing_task_id(self):
        """Test TaskResult requires task_id field."""
        with pytest.raises(ValidationError) as exc_info:
            TaskResult(
                status="success",
                output_data={},
                execution_time_ms=100.0
                # Missing: task_id
            )

        errors = exc_info.value.errors()
        assert any(error['loc'] == ('task_id',) for error in errors)

    def test_task_result_missing_status(self):
        """Test TaskResult requires status field."""
        with pytest.raises(ValidationError) as exc_info:
            TaskResult(
                task_id="task-123",
                output_data={},
                execution_time_ms=100.0
                # Missing: status
            )

        errors = exc_info.value.errors()
        assert any(error['loc'] == ('status',) for error in errors)

    def test_task_result_missing_execution_time(self):
        """Test TaskResult requires execution_time_ms field."""
        with pytest.raises(ValidationError) as exc_info:
            TaskResult(
                task_id="task-123",
                status="success",
                output_data={}
                # Missing: execution_time_ms
            )

        errors = exc_info.value.errors()
        assert any(error['loc'] == ('execution_time_ms',) for error in errors)

    def test_agent_message_missing_source_agent(self):
        """Test AgentMessage requires source_agent field."""
        with pytest.raises(ValidationError) as exc_info:
            AgentMessage(
                target_agent="agent-b",
                message_type="test",
                payload={},
                context_id="ctx-123"
                # Missing: source_agent
            )

        errors = exc_info.value.errors()
        assert any(error['loc'] == ('source_agent',) for error in errors)

    def test_agent_message_missing_target_agent(self):
        """Test AgentMessage requires target_agent field."""
        with pytest.raises(ValidationError) as exc_info:
            AgentMessage(
                source_agent="agent-a",
                message_type="test",
                payload={},
                context_id="ctx-123"
                # Missing: target_agent
            )

        errors = exc_info.value.errors()
        assert any(error['loc'] == ('target_agent',) for error in errors)

    def test_agent_message_missing_message_type(self):
        """Test AgentMessage requires message_type field."""
        with pytest.raises(ValidationError) as exc_info:
            AgentMessage(
                source_agent="agent-a",
                target_agent="agent-b",
                payload={},
                context_id="ctx-123"
                # Missing: message_type
            )

        errors = exc_info.value.errors()
        assert any(error['loc'] == ('message_type',) for error in errors)

    def test_agent_message_missing_payload(self):
        """Test AgentMessage requires payload field."""
        with pytest.raises(ValidationError) as exc_info:
            AgentMessage(
                source_agent="agent-a",
                target_agent="agent-b",
                message_type="test",
                context_id="ctx-123"
                # Missing: payload
            )

        errors = exc_info.value.errors()
        assert any(error['loc'] == ('payload',) for error in errors)

    def test_agent_message_missing_context_id(self):
        """Test AgentMessage requires context_id field (Context Protection)."""
        with pytest.raises(ValidationError) as exc_info:
            AgentMessage(
                source_agent="agent-a",
                target_agent="agent-b",
                message_type="test",
                payload={}
                # Missing: context_id
            )

        errors = exc_info.value.errors()
        assert any(error['loc'] == ('context_id',) for error in errors)
