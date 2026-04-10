"""
Test EventBus and event hooks.

Tests cover:
- Publish-Subscribe mechanics
- Multiple subscribers
- Exception handling
- Event payloads (TaskEvent, SkillExecutionEvent)
- Event filtering
"""

import pytest

from core.auto_dev.event_hooks import EventBus, SkillExecutionEvent, TaskEvent


# =============================================================================
# Publish-Subscribe Tests
# =============================================================================

class TestEventBusPublishSubscribe:
    """Test EventBus.publish() delivers events to subscribers."""

    def test_emit_task_fail_calls_all_handlers(self):
        """Test emit_task_fail() calls all registered handlers."""
        bus = EventBus()
        handler_calls = []

        async def handler1(event):
            handler_calls.append(("handler1", event.episode_id))

        async def handler2(event):
            handler_calls.append(("handler2", event.episode_id))

        bus.on_task_fail(handler1)
        bus.on_task_fail(handler2)

        event = TaskEvent(
            episode_id="ep-001",
            agent_id="agent-001",
            tenant_id="tenant-001",
            task_description="Test task",
            outcome="failure",
        )

        import asyncio
        asyncio.run(bus.emit_task_fail(event))

        assert len(handler_calls) == 2
        assert handler_calls[0] == ("handler1", "ep-001")
        assert handler_calls[1] == ("handler2", "ep-001")

    def test_emit_task_success_calls_all_handlers(self):
        """Test emit_task_success() calls all registered handlers."""
        bus = EventBus()
        handler_calls = []

        async def handler(event):
            handler_calls.append(event.task_description)

        bus.on_task_success(handler)

        event = TaskEvent(
            episode_id="ep-001",
            agent_id="agent-001",
            tenant_id="tenant-001",
            task_description="Successful task",
            outcome="success",
        )

        import asyncio
        asyncio.run(bus.emit_task_success(event))

        assert len(handler_calls) == 1
        assert handler_calls[0] == "Successful task"

    def test_emit_skill_execution_calls_all_handlers(self):
        """Test emit_skill_execution() calls all registered handlers."""
        bus = EventBus()
        handler_calls = []

        async def handler(event):
            handler_calls.append(("skill", event.skill_name, event.success))

        bus.on_skill_execution(handler)

        event = SkillExecutionEvent(
            execution_id="exec-001",
            agent_id="agent-001",
            tenant_id="tenant-001",
            skill_id="skill-001",
            skill_name="test_skill",
            success=True,
        )

        import asyncio
        asyncio.run(bus.emit_skill_execution(event))

        assert len(handler_calls) == 1
        assert handler_calls[0] == ("skill", "test_skill", True)

    def test_verify_event_payload_delivery(self):
        """Test event payload is delivered correctly to handlers."""
        bus = EventBus()
        received_events = []

        async def handler(event):
            received_events.append(event)

        bus.on_task_fail(handler)

        event = TaskEvent(
            episode_id="ep-001",
            agent_id="agent-001",
            tenant_id="tenant-001",
            task_description="Test task",
            error_trace="Error: something failed",
            outcome="failure",
            metadata={"key": "value"},
        )

        import asyncio
        asyncio.run(bus.emit_task_fail(event))

        assert len(received_events) == 1
        received = received_events[0]
        assert received.episode_id == "ep-001"
        assert received.agent_id == "agent-001"
        assert received.tenant_id == "tenant-001"
        assert received.task_description == "Test task"
        assert received.error_trace == "Error: something failed"
        assert received.outcome == "failure"
        assert received.metadata == {"key": "value"}


# =============================================================================
# Multiple Subscribers Tests
# =============================================================================

class TestEventBusMultipleSubscribers:
    """Test multiple subscribers receive same event."""

    def test_multiple_handlers_receive_event(self):
        """Test all handlers receive the same event."""
        bus = EventBus()
        handler1_calls = []
        handler2_calls = []
        handler3_calls = []

        async def handler1(event):
            handler1_calls.append(event.episode_id)

        async def handler2(event):
            handler2_calls.append(event.episode_id)

        async def handler3(event):
            handler3_calls.append(event.episode_id)

        bus.on_task_fail(handler1)
        bus.on_task_fail(handler2)
        bus.on_task_fail(handler3)

        event = TaskEvent(
            episode_id="ep-001",
            agent_id="agent-001",
            tenant_id="tenant-001",
            task_description="Test",
            outcome="failure",
        )

        import asyncio
        asyncio.run(bus.emit_task_fail(event))

        assert len(handler1_calls) == 1
        assert len(handler2_calls) == 1
        assert len(handler3_calls) == 1
        assert handler1_calls[0] == "ep-001"
        assert handler2_calls[0] == "ep-001"
        assert handler3_calls[0] == "ep-001"

    def test_handler_execution_order(self):
        """Test handlers execute in registration order."""
        bus = EventBus()
        execution_order = []

        async def handler1(event):
            execution_order.append(1)

        async def handler2(event):
            execution_order.append(2)

        async def handler3(event):
            execution_order.append(3)

        # Register in order 1, 2, 3
        bus.on_task_fail(handler1)
        bus.on_task_fail(handler2)
        bus.on_task_fail(handler3)

        event = TaskEvent(
            episode_id="ep-001",
            agent_id="agent-001",
            tenant_id="tenant-001",
            task_description="Test",
            outcome="failure",
        )

        import asyncio
        asyncio.run(bus.emit_task_fail(event))

        assert execution_order == [1, 2, 3]

    def test_different_event_types_separate_handlers(self):
        """Test handlers for different event types don't interfere."""
        bus = EventBus()
        fail_calls = []
        success_calls = []
        skill_calls = []

        async def fail_handler(event):
            fail_calls.append("fail")

        async def success_handler(event):
            success_calls.append("success")

        async def skill_handler(event):
            skill_calls.append("skill")

        bus.on_task_fail(fail_handler)
        bus.on_task_success(success_handler)
        bus.on_skill_execution(skill_handler)

        fail_event = TaskEvent(
            episode_id="ep-001",
            agent_id="agent-001",
            tenant_id="tenant-001",
            task_description="Test",
            outcome="failure",
        )

        import asyncio
        asyncio.run(bus.emit_task_fail(fail_event))

        assert len(fail_calls) == 1
        assert len(success_calls) == 0
        assert len(skill_calls) == 0


# =============================================================================
# Exception Handling Tests
# =============================================================================

class TestEventBusExceptionHandling:
    """Test subscriber exceptions don't crash event bus."""

    def test_handler_exception_doesnt_crash_bus(self):
        """Test exception in handler doesn't crash event bus."""
        bus = EventBus()
        handler1_calls = []
        handler2_calls = []

        async def handler1(event):
            handler1_calls.append("handler1")
            raise ValueError("Simulated error in handler1")

        async def handler2(event):
            handler2_calls.append("handler2")

        bus.on_task_fail(handler1)
        bus.on_task_fail(handler2)

        event = TaskEvent(
            episode_id="ep-001",
            agent_id="agent-001",
            tenant_id="tenant-001",
            task_description="Test",
            outcome="failure",
        )

        import asyncio
        # Should not raise exception
        asyncio.run(bus.emit_task_fail(event))

        # Both handlers should have been called
        assert len(handler1_calls) == 1
        assert len(handler2_calls) == 1

    def test_multiple_handler_exceptions(self):
        """Test multiple handler exceptions are handled gracefully."""
        bus = EventBus()
        handler_calls = []

        async def handler1(event):
            handler_calls.append("h1")
            raise Exception("Error 1")

        async def handler2(event):
            handler_calls.append("h2")
            raise ValueError("Error 2")

        async def handler3(event):
            handler_calls.append("h3")
            # No error

        bus.on_task_fail(handler1)
        bus.on_task_fail(handler2)
        bus.on_task_fail(handler3)

        event = TaskEvent(
            episode_id="ep-001",
            agent_id="agent-001",
            tenant_id="tenant-001",
            task_description="Test",
            outcome="failure",
        )

        import asyncio
        asyncio.run(bus.emit_task_fail(event))

        assert handler_calls == ["h1", "h2", "h3"]

    def test_exception_logged_with_handler_name(self, caplog):
        """Test exceptions are logged with handler name."""
        import logging
        bus = EventBus()

        async def failing_handler(event):
            raise RuntimeError("Test error")

        bus.on_task_fail(failing_handler)

        event = TaskEvent(
            episode_id="ep-001",
            agent_id="agent-001",
            tenant_id="tenant-001",
            task_description="Test",
            outcome="failure",
        )

        import asyncio
        with caplog.at_level(logging.ERROR):
            asyncio.run(bus.emit_task_fail(event))

        # Check error was logged
        assert any("failing_handler" in record.message for record in caplog.records)
        assert any("Test error" in record.message for record in caplog.records)


# =============================================================================
# Event Payload Tests
# =============================================================================

class TestEventBusEventPayloads:
    """Test TaskEvent and SkillExecutionEvent payloads."""

    def test_task_event_fields(self):
        """Test TaskEvent fields (episode_id, agent_id, error_trace, outcome)."""
        event = TaskEvent(
            episode_id="ep-001",
            agent_id="agent-001",
            tenant_id="tenant-001",
            task_description="Process data",
            error_trace="ValueError: invalid format",
            outcome="failure",
            metadata={"retry_count": 3},
        )

        assert event.episode_id == "ep-001"
        assert event.agent_id == "agent-001"
        assert event.tenant_id == "tenant-001"
        assert event.task_description == "Process data"
        assert event.error_trace == "ValueError: invalid format"
        assert event.outcome == "failure"
        assert event.metadata == {"retry_count": 3}

    def test_task_event_default_values(self):
        """Test TaskEvent default values."""
        event = TaskEvent(
            episode_id="ep-001",
            agent_id="agent-001",
            tenant_id="tenant-001",
        )

        assert event.task_description == ""
        assert event.error_trace is None
        assert event.outcome == ""
        assert event.metadata == {}

    def test_skill_execution_event_fields(self):
        """Test SkillExecutionEvent fields (execution_id, skill_id, token_usage)."""
        event = SkillExecutionEvent(
            execution_id="exec-001",
            agent_id="agent-001",
            tenant_id="tenant-001",
            skill_id="skill-001",
            skill_name="data_processor",
            execution_seconds=5.2,
            token_usage=3500,
            success=True,
            output="Processed 100 records",
            metadata={"input_size": 100},
        )

        assert event.execution_id == "exec-001"
        assert event.agent_id == "agent-001"
        assert event.tenant_id == "tenant-001"
        assert event.skill_id == "skill-001"
        assert event.skill_name == "data_processor"
        assert event.execution_seconds == 5.2
        assert event.token_usage == 3500
        assert event.success is True
        assert event.output == "Processed 100 records"
        assert event.metadata == {"input_size": 100}

    def test_skill_execution_event_default_values(self):
        """Test SkillExecutionEvent default values."""
        event = SkillExecutionEvent(
            execution_id="exec-001",
            agent_id="agent-001",
            tenant_id="tenant-001",
            skill_id="skill-001",
        )

        assert event.skill_name == ""
        assert event.execution_seconds == 0.0
        assert event.token_usage == 0
        assert event.success is False
        assert event.output == ""
        assert event.metadata == {}

    def test_metadata_dictionary_handling(self):
        """Test metadata dictionary can store arbitrary data."""
        event = TaskEvent(
            episode_id="ep-001",
            agent_id="agent-001",
            tenant_id="tenant-001",
            metadata={
                "nested": {"key": "value"},
                "list": [1, 2, 3],
                "number": 42,
                "boolean": True,
            },
        )

        assert event.metadata["nested"]["key"] == "value"
        assert event.metadata["list"] == [1, 2, 3]
        assert event.metadata["number"] == 42
        assert event.metadata["boolean"] is True


# =============================================================================
# Event Filtering Tests
# =============================================================================

class TestEventBusEventFiltering:
    """Test event filtering by agent_id and tenant_id."""

    def test_filter_by_agent_id(self):
        """Test filtering events by agent_id in handler."""
        bus = EventBus()
        agent1_events = []
        agent2_events = []

        async def agent1_handler(event):
            if event.agent_id == "agent-001":
                agent1_events.append(event)

        async def agent2_handler(event):
            if event.agent_id == "agent-002":
                agent2_events.append(event)

        bus.on_task_fail(agent1_handler)
        bus.on_task_fail(agent2_handler)

        event1 = TaskEvent(
            episode_id="ep-001",
            agent_id="agent-001",
            tenant_id="tenant-001",
            task_description="Test",
            outcome="failure",
        )

        event2 = TaskEvent(
            episode_id="ep-002",
            agent_id="agent-002",
            tenant_id="tenant-001",
            task_description="Test",
            outcome="failure",
        )

        import asyncio
        asyncio.run(bus.emit_task_fail(event1))
        asyncio.run(bus.emit_task_fail(event2))

        assert len(agent1_events) == 1
        assert len(agent2_events) == 1
        assert agent1_events[0].agent_id == "agent-001"
        assert agent2_events[0].agent_id == "agent-002"

    def test_filter_by_tenant_id(self):
        """Test filtering events by tenant_id in handler."""
        bus = EventBus()
        tenant1_events = []
        tenant2_events = []

        async def tenant1_handler(event):
            if event.tenant_id == "tenant-001":
                tenant1_events.append(event)

        async def tenant2_handler(event):
            if event.tenant_id == "tenant-002":
                tenant2_events.append(event)

        bus.on_task_fail(tenant1_handler)
        bus.on_task_fail(tenant2_handler)

        event1 = TaskEvent(
            episode_id="ep-001",
            agent_id="agent-001",
            tenant_id="tenant-001",
            task_description="Test",
            outcome="failure",
        )

        event2 = TaskEvent(
            episode_id="ep-002",
            agent_id="agent-002",
            tenant_id="tenant-002",
            task_description="Test",
            outcome="failure",
        )

        import asyncio
        asyncio.run(bus.emit_task_fail(event1))
        asyncio.run(bus.emit_task_fail(event2))

        assert len(tenant1_events) == 1
        assert len(tenant2_events) == 1
        assert tenant1_events[0].tenant_id == "tenant-001"
        assert tenant2_events[0].tenant_id == "tenant-002"

    def test_filter_by_event_type(self):
        """Test filtering by event type (success vs failure)."""
        bus = EventBus()
        failures = []
        successes = []

        async def failure_handler(event):
            if event.outcome == "failure":
                failures.append(event)

        async def success_handler(event):
            if event.outcome == "success":
                successes.append(event)

        bus.on_task_fail(failure_handler)
        bus.on_task_success(success_handler)

        fail_event = TaskEvent(
            episode_id="ep-001",
            agent_id="agent-001",
            tenant_id="tenant-001",
            task_description="Test",
            outcome="failure",
        )

        success_event = TaskEvent(
            episode_id="ep-002",
            agent_id="agent-001",
            tenant_id="tenant-001",
            task_description="Test",
            outcome="success",
        )

        import asyncio
        asyncio.run(bus.emit_task_fail(fail_event))
        asyncio.run(bus.emit_task_success(success_event))

        assert len(failures) == 1
        assert len(successes) == 1
        assert failures[0].outcome == "failure"
        assert successes[0].outcome == "success"


# =============================================================================
# EventBus Clear Tests
# =============================================================================

class TestEventBusClear:
    """Test EventBus.clear() removes all handlers."""

    def test_clear_removes_all_handlers(self):
        """Test clear() removes all registered handlers."""
        bus = EventBus()
        handler_calls = []

        async def handler1(event):
            handler_calls.append("h1")

        async def handler2(event):
            handler_calls.append("h2")

        bus.on_task_fail(handler1)
        bus.on_task_fail(handler2)

        # Clear all handlers
        bus.clear()

        event = TaskEvent(
            episode_id="ep-001",
            agent_id="agent-001",
            tenant_id="tenant-001",
            task_description="Test",
            outcome="failure",
        )

        import asyncio
        asyncio.run(bus.emit_task_fail(event))

        # No handlers should be called
        assert len(handler_calls) == 0

    def test_clear_all_event_types(self):
        """Test clear() removes handlers for all event types."""
        bus = EventBus()
        calls = []

        async def fail_handler(event):
            calls.append("fail")

        async def success_handler(event):
            calls.append("success")

        async def skill_handler(event):
            calls.append("skill")

        bus.on_task_fail(fail_handler)
        bus.on_task_success(success_handler)
        bus.on_skill_execution(skill_handler)

        bus.clear()

        import asyncio
        asyncio.run(bus.emit_task_fail(
            TaskEvent(episode_id="ep-001", agent_id="agent-001", tenant_id="tenant-001")
        ))
        asyncio.run(bus.emit_task_success(
            TaskEvent(episode_id="ep-001", agent_id="agent-001", tenant_id="tenant-001")
        ))
        asyncio.run(bus.emit_skill_execution(
            SkillExecutionEvent(
                execution_id="exec-001",
                agent_id="agent-001",
                tenant_id="tenant-001",
                skill_id="skill-001",
            )
        ))

        assert len(calls) == 0
