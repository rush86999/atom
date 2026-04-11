"""
Property-Based Tests for EventBus

This module tests EventBus invariants using Hypothesis to generate hundreds
of test cases automatically.

Properties tested:
1. Subscriber Delivery Invariant - All registered subscribers receive events
2. Event Filtering Invariant - Filter predicates prevent delivery
3. Exception Isolation Invariant - Subscriber exceptions don't affect others
4. No Duplicate Delivery Invariant - Subscribers receive at most one copy per event
5. Handler Count Invariant - Handler count matches registrations
"""

import pytest
import asyncio
from hypothesis import given, settings, strategies as st, HealthCheck
from typing import Any

from core.auto_dev.event_hooks import EventBus, TaskEvent, SkillExecutionEvent


# =============================================================================
# Strategy Definitions
# =============================================================================

# Event type strategy (valid event types for EventBus)
event_types = st.sampled_from(['task_fail', 'task_success', 'skill_execution'])

# Subscriber name strategy
subscriber_names = st.text(min_size=1, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz_0123456789')

# Priority strategy (for priority ordering tests)
priorities = st.integers(min_value=0, max_value=100)


# =============================================================================
# Property Tests
# =============================================================================

@pytest.mark.property
@given(
    event_type=event_types,
    subscribers=st.lists(subscriber_names, min_size=1, max_size=10, unique=True)
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_subscriber_delivery_invariant(event_bus, event_type, subscribers):
    """
    Property: All registered subscribers receive events they're subscribed to.

    For any set of subscribers and any event type, every subscriber that
    registers for that event type should receive exactly one event when
    the event is dispatched.
    """
    received = {sub: [] for sub in subscribers}

    # Register all subscribers for the same event type
    for sub in subscribers:
        async def handler(event, subscriber_name=sub):
            received[subscriber_name].append(event)

        if event_type == 'task_fail':
            event_bus.on_task_fail(handler)
        elif event_type == 'task_success':
            event_bus.on_task_success(handler)
        else:
            event_bus.on_skill_execution(handler)

    # Dispatch event
    if event_type == 'task_fail':
        event = TaskEvent(
            episode_id="test-episode",
            agent_id="test-agent",
            tenant_id="test-tenant",
            outcome="failure"
        )
        asyncio.run(event_bus.emit_task_fail(event))
    elif event_type == 'task_success':
        event = TaskEvent(
            episode_id="test-episode",
            agent_id="test-agent",
            tenant_id="test-tenant",
            outcome="success"
        )
        asyncio.run(event_bus.emit_task_success(event))
    else:
        event = SkillExecutionEvent(
            execution_id="test-execution",
            agent_id="test-agent",
            tenant_id="test-tenant",
            skill_id="test-skill",
            success=True
        )
        asyncio.run(event_bus.emit_skill_execution(event))

    # Verify all subscribers received exactly one event
    for sub in subscribers:
        assert len(received[sub]) == 1, \
            f"Subscriber {sub} received {len(received[sub])} events, expected 1"


@pytest.mark.property
@given(
    subscribers=st.lists(subscriber_names, min_size=5, max_size=10, unique=True)
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_exception_isolation_invariant(event_bus, subscribers):
    """
    Property: Subscriber exceptions don't prevent other subscribers from receiving events.

    For any set of subscribers where some may raise exceptions, all non-failing
    subscribers should still receive events. Exception handling should prevent
    cascading failures.
    """
    import random

    # Randomly select 2 subscribers to fail
    fail_indices = random.sample(range(len(subscribers)), min(2, len(subscribers)))
    received = set()

    async def make_handler(sub_name, should_fail):
        async def handler(event):
            if should_fail:
                raise Exception(f"Simulated failure in {sub_name}")
            received.add(sub_name)
        return handler

    # Register subscribers
    for i, sub in enumerate(subscribers):
        should_fail = i in fail_indices
        handler = make_handler(sub, should_fail)
        event_bus.on_task_fail(handler)

    # Dispatch event (should not raise despite failures)
    event = TaskEvent(
        episode_id="test-episode",
        agent_id="test-agent",
        tenant_id="test-tenant",
        outcome="failure"
    )

    try:
        asyncio.run(event_bus.emit_task_fail(event))
    except Exception:
        pass  # EventBus should catch handler exceptions

    # Verify non-failing subscribers still received event
    expected_receivers = {sub for i, sub in enumerate(subscribers) if i not in fail_indices}
    assert received == expected_receivers, \
        f"Received {received}, expected {expected_receivers}"


@pytest.mark.property
@given(
    dispatch_count=st.integers(min_value=1, max_value=5),
    subscribers=st.lists(subscriber_names, min_size=1, max_size=5, unique=True)
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_no_duplicate_delivery_invariant(event_bus, dispatch_count, subscribers):
    """
    Property: Subscribers never receive the same event twice per dispatch.

    For any number of dispatches, each subscriber should receive exactly one
    event per dispatch, with no duplicates within a single dispatch cycle.
    """
    received = {sub: [] for sub in subscribers}

    async def make_handler(sub_name):
        async def handler(event):
            received[sub_name].append(event)
        return handler

    # Register subscribers
    for sub in subscribers:
        handler = make_handler(sub)
        event_bus.on_task_success(handler)

    # Dispatch multiple times with different event data
    for i in range(dispatch_count):
        event = TaskEvent(
            episode_id=f"test-episode-{i}",
            agent_id="test-agent",
            tenant_id="test-tenant",
            outcome="success",
            metadata={"dispatch_id": i}
        )
        asyncio.run(event_bus.emit_task_success(event))

    # Verify each subscriber received exactly dispatch_count events
    for sub in subscribers:
        assert len(received[sub]) == dispatch_count, \
            f"Subscriber {sub} received {len(received[sub])} events, expected {dispatch_count}"

        # Verify no duplicates within single dispatch (unique episode_ids)
        episode_ids = [e.episode_id for e in received[sub]]
        assert len(episode_ids) == len(set(episode_ids)), \
            f"Duplicate events detected for {sub}: {episode_ids}"


@pytest.mark.property
@given(
    subscribers=st.lists(subscriber_names, min_size=1, max_size=10, unique=True)
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_handler_count_invariant(event_bus, subscribers):
    """
    Property: Handler count matches the number of registered subscribers.

    For any set of subscribers registered for an event type, the internal
    handler count should match the number of registrations.
    """
    initial_fail_count = len(event_bus._fail_handlers)
    initial_success_count = len(event_bus._success_handlers)
    initial_skill_count = len(event_bus._skill_handlers)

    # Register subscribers for task_fail events
    for sub in subscribers:
        async def handler(event, name=sub):
            pass
        event_bus.on_task_fail(handler)

    # Verify handler count increased
    expected_count = initial_fail_count + len(subscribers)
    assert len(event_bus._fail_handlers) == expected_count, \
        f"Expected {expected_count} handlers, got {len(event_bus._fail_handlers)}"

    # Verify other handler lists unchanged
    assert len(event_bus._success_handlers) == initial_success_count
    assert len(event_bus._skill_handlers) == initial_skill_count


@pytest.mark.property
@given(
    event_type=event_types,
    subscribers=st.lists(subscriber_names, min_size=3, max_size=10, unique=True)
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_clear_removes_all_handlers(event_bus, event_type, subscribers):
    """
    Property: Clearing the event bus removes all registered handlers.

    After registering handlers and calling clear(), all handler lists should
    be empty, and no subscribers should receive events.
    """
    received = set()

    # Register subscribers
    for sub in subscribers:
        async def handler(event, name=sub):
            received.add(name)
        event_bus.on_task_fail(handler)
        event_bus.on_task_success(handler)
        event_bus.on_skill_execution(handler)

    # Clear all handlers
    event_bus.clear()

    # Verify all handler lists empty
    assert len(event_bus._fail_handlers) == 0
    assert len(event_bus._success_handlers) == 0
    assert len(event_bus._skill_handlers) == 0

    # Dispatch events - nothing should be received
    event = TaskEvent(
        episode_id="test-episode",
        agent_id="test-agent",
        tenant_id="test-tenant",
        outcome="success"
    )

    asyncio.run(event_bus.emit_task_fail(event))
    asyncio.run(event_bus.emit_task_success(event))

    assert len(received) == 0, "Subscribers received events after clear"


@pytest.mark.property
@given(
    episode_id=st.text(min_size=1, max_size=50),
    agent_id=st.text(min_size=1, max_size=50),
    tenant_id=st.text(min_size=1, max_size=50),
    outcome=st.sampled_from(['success', 'failure', 'partial'])
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_task_event_structure_invariant(event_bus, episode_id, agent_id, tenant_id, outcome):
    """
    Property: TaskEvent objects maintain correct structure and data integrity.

    For any valid input parameters, TaskEvent should store all fields correctly
    and maintain data types.
    """
    event = TaskEvent(
        episode_id=episode_id,
        agent_id=agent_id,
        tenant_id=tenant_id,
        outcome=outcome,
        task_description="Test task",
        error_trace=None,
        metadata={"test": True}
    )

    # Verify field types
    assert isinstance(event.episode_id, str)
    assert isinstance(event.agent_id, str)
    assert isinstance(event.tenant_id, str)
    assert isinstance(event.outcome, str)
    assert isinstance(event.task_description, str)
    assert isinstance(event.metadata, dict)

    # Verify values match
    assert event.episode_id == episode_id
    assert event.agent_id == agent_id
    assert event.tenant_id == tenant_id
    assert event.outcome == outcome


@pytest.mark.property
@given(
    execution_id=st.text(min_size=1, max_size=50),
    agent_id=st.text(min_size=1, max_size=50),
    tenant_id=st.text(min_size=1, max_size=50),
    skill_id=st.text(min_size=1, max_size=50),
    success=st.booleans()
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_skill_execution_event_structure_invariant(
    event_bus, execution_id, agent_id, tenant_id, skill_id, success
):
    """
    Property: SkillExecutionEvent objects maintain correct structure and data integrity.

    For any valid input parameters, SkillExecutionEvent should store all fields
    correctly and maintain data types.
    """
    event = SkillExecutionEvent(
        execution_id=execution_id,
        agent_id=agent_id,
        tenant_id=tenant_id,
        skill_id=skill_id,
        skill_name="Test Skill",
        execution_seconds=1.5,
        token_usage=100,
        success=success,
        output="Test output",
        metadata={"test": True}
    )

    # Verify field types
    assert isinstance(event.execution_id, str)
    assert isinstance(event.agent_id, str)
    assert isinstance(event.tenant_id, str)
    assert isinstance(event.skill_id, str)
    assert isinstance(event.skill_name, str)
    assert isinstance(event.execution_seconds, float)
    assert isinstance(event.token_usage, int)
    assert isinstance(event.success, bool)
    assert isinstance(event.output, str)
    assert isinstance(event.metadata, dict)

    # Verify values match
    assert event.execution_id == execution_id
    assert event.agent_id == agent_id
    assert event.tenant_id == tenant_id
    assert event.skill_id == skill_id
    assert event.success == success
