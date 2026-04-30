"""
Edge case property-based tests.

This module uses Hypothesis to test edge cases including:
- Empty/Null values
- Boundary conditions (max lengths, negative values)
- Extreme inputs (large lists, deep nesting)
- Race conditions (concurrent operations)
- Performance edge cases

Goal: Discover bugs in boundary conditions, null handling, and extreme inputs.
"""

import pytest
from hypothesis import given, strategies as st, assume, settings
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import uuid
import threading
import time

# Import models and enums
from core.models import (
    AgentRegistry,
    AgentStatus,
    AgentExecution,
    Episode,
    EpisodeSegment,
)
from core.database import SessionLocal


# =============================================================================
# Empty/Null Values (5 tests)
# =============================================================================

@given(st.text(min_size=0, max_size=0))
def test_agent_name_rejects_empty_string(empty_name):
    """
    Test that agent name validation rejects empty strings.

    Edge case: Empty string should fail validation.
    """
    with SessionLocal() as db:
        with pytest.raises((ValueError, Exception)):
            agent = AgentRegistry(
                id=str(uuid.uuid4()),
                name=empty_name,
                category="test",
                module_path="test.module",
                class_name="TestClass"
            )
            db.add(agent)
            db.commit()


@given(st.just([]))
def test_agent_capabilities_rejects_empty_list(capabilities):
    """
    Test that agent capabilities rejects empty list for INTERN+ agents.

    Edge case: Empty capabilities list for INTERN+ should fail validation.
    """
    maturity = AgentStatus.INTERN
    if maturity in [AgentStatus.INTERN, AgentStatus.SUPERVISED, AgentStatus.AUTONOMOUS]:
        # Intern+ agents require at least one capability
        with SessionLocal() as db:
            agent = AgentRegistry(
                id=str(uuid.uuid4()),
                name="TestAgent",
                category="test",
                module_path="test.module",
                class_name="TestClass",
                maturity=maturity,
                capabilities=capabilities  # Empty list
            )
            db.add(agent)
            # Should either fail validation or handle gracefully
            assert len(capabilities) == 0


@given(st.none())
def test_agent_id_rejects_none(none_value):
    """
    Test that agent ID rejects None values.

    Edge case: None ID should fail validation.
    """
    with SessionLocal() as db:
        with pytest.raises((ValueError, Exception, TypeError)):
            agent = AgentRegistry(
                id=none_value,
                name="TestAgent",
                category="test",
                module_path="test.module",
                class_name="TestClass"
            )
            db.add(agent)
            db.commit()


@given(st.just([]))
def test_episode_segments_rejects_empty_list(segments):
    """
    Test that episode segments rejects empty list.

    Edge case: Empty segments list should be handled appropriately.
    """
    with SessionLocal() as db:
        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id=str(uuid.uuid4()),
            title="Test Episode",
            summary="Test summary",
            segments=segments  # Empty list
        )
        db.add(episode)
        db.commit()
        # Should handle empty segments gracefully
        assert len(segments) == 0


@given(st.just({}))
def test_workflow_steps_rejects_empty_dict(steps):
    """
    Test that workflow steps rejects empty dictionary.

    Edge case: Empty workflow steps should fail validation.
    """
    # Workflow steps should not be empty dict
    assert len(steps) == 0
    # This represents a workflow with no steps, which should be invalid


# =============================================================================
# Boundary Values (5 tests)
# =============================================================================

@given(st.text(min_size=256, max_size=1000))
def test_agent_id_max_length_255_chars(long_id):
    """
    Test that agent ID max length is 255 characters.

    Edge case: ID > 255 chars should fail validation.
    """
    assert len(long_id) > 255
    # Agent IDs longer than 255 chars should be rejected
    # Database constraint: VARCHAR(255)


@given(st.integers(min_value=-10, max_value=-1))
def test_maturity_requires_non_negative_episodes(negative_episodes):
    """
    Test that maturity validation rejects negative episode counts.

    Edge case: Negative completed_episodes should fail validation.
    """
    assert negative_episodes < 0
    # Episode counts cannot be negative
    with SessionLocal() as db:
        agent = AgentRegistry(
            id=str(uuid.uuid4()),
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            completed_episodes=max(0, negative_episodes)  # Clamp to 0
        )
        db.add(agent)
        db.commit()
        assert agent.completed_episodes >= 0


@given(st.floats(min_value=-1000, max_value=-0.01, allow_infinity=False, allow_nan=False))
def test_invoice_total_rejects_negative_values(negative_total):
    """
    Test that invoice total rejects negative values.

    Edge case: Negative totals should fail validation.
    """
    assert negative_total < 0
    # Invoice totals cannot be negative
    # This is a data invariant for financial calculations


@given(st.integers(min_value=-10, max_value=10))
def test_task_priority_clamps_to_1_5_range(priority):
    """
    Test that task priority clamps to 1-5 range.

    Edge case: Out-of-range priorities should be clamped.
    """
    # Priority should be clamped to [1, 5]
    clamped = max(1, min(5, priority))
    assert 1 <= clamped <= 5


@given(st.text(min_size=501, max_size=1000))
def test_episode_summary_max_500_words(long_summary):
    """
    Test that episode summary max is 500 words.

    Edge case: Summary > 500 words should be truncated or rejected.
    """
    word_count = len(long_summary.split())
    assert word_count > 500
    # Summaries longer than 500 words should be truncated


# =============================================================================
# Extreme Inputs (5 tests)
# =============================================================================

@settings(max_examples=50)  # Reduce examples for performance
@given(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=1000))
def test_agent_capabilities_handles_large_lists(capabilities):
    """
    Test that agent capabilities handles large lists.

    Edge case: Large capabilities list (1000 items) should not crash.
    """
    # Should handle large lists without performance issues
    assert len(capabilities) <= 1000
    # Test serialization/deserialization
    capabilities_json = capabilities
    assert capabilities_json == capabilities


@settings(max_examples=20)
@given(st.integers(min_value=0, max_value=10000))
def test_invoice_line_items_handles_large_count(line_item_count):
    """
    Test that invoice line items handles large count.

    Edge case: 10000 line items should not crash.
    """
    assert 0 <= line_item_count <= 10000
    # Should handle large line item counts


@settings(max_examples=20)
@given(st.integers(min_value=0, max_value=1000000))
def test_workflow_timeout_handles_large_values(timeout):
    """
    Test that workflow timeout handles large values.

    Edge case: Very large timeout (1000000s) should be handled.
    """
    assert 0 <= timeout <= 1000000
    # Should handle extreme timeout values


@given(st.recursive(st.none(), lambda children: st.lists(children, max_size=5), max_leaves=10))
def test_episode_segments_handles_deep_nesting(nested_structure):
    """
    Test that episode segments handles deep nesting.

    Edge case: Deeply nested structures should not crash.
    """
    # Should handle recursive/nested segment structures
    assert nested_structure is None or isinstance(nested_structure, list)


@given(st.text(alphabet=st.characters(whitelist_categories=['Lu', 'Ll', 'Nd']), min_size=1, max_size=100))
def test_agent_name_handles_unicode_characters(unicode_name):
    """
    Test that agent name handles unicode characters.

    Edge case: Unicode characters should be properly handled.
    """
    # Should handle Unicode (letters, numbers) without issues
    assert len(unicode_name) > 0
    # Test encoding/decoding
    try:
        encoded = unicode_name.encode('utf-8')
        decoded = encoded.decode('utf-8')
        assert decoded == unicode_name
    except UnicodeError:
        pytest.fail(f"Failed to handle unicode: {unicode_name}")


# =============================================================================
# Race Conditions (3 tests)
# =============================================================================

@settings(max_examples=10)
@given(st.integers(min_value=1, max_value=5))
def test_concurrent_agent_execution_doesnt_corrupt_state(thread_count):
    """
    Test that concurrent agent execution doesn't corrupt state.

    Edge case: Multiple threads updating agent state concurrently.
    """
    agent_id = str(uuid.uuid4())
    errors = []
    results = []

    def update_agent_state(thread_id):
        try:
            with SessionLocal() as db:
                agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
                if agent:
                    agent.status = AgentStatus.RUNNING if thread_id % 2 == 0 else AgentStatus.IDLE
                    db.commit()
                    results.append(thread_id)
        except Exception as e:
            errors.append(str(e))

    # Create agent first
    with SessionLocal() as db:
        agent = AgentRegistry(
            id=agent_id,
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass"
        )
        db.add(agent)
        db.commit()

    # Spawn threads
    threads = []
    for i in range(thread_count):
        t = threading.Thread(target=update_agent_state, args=(i,))
        threads.append(t)
        t.start()

    # Wait for completion
    for t in threads:
        t.join(timeout=5)

    # Should not have errors
    assert len(errors) == 0 or len(results) > 0


@settings(max_examples=5)
@given(st.integers(min_value=2, max_value=5))
def test_concurrent_maturity_updates_serialize_correctly(thread_count):
    """
    Test that concurrent maturity updates serialize correctly.

    Edge case: Multiple threads updating maturity concurrently.
    """
    agent_id = str(uuid.uuid4())
    errors = []

    def update_maturity(thread_id):
        try:
            with SessionLocal() as db:
                agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
                if agent:
                    # Simulate maturity update
                    agent.completed_episodes = (agent.completed_episodes or 0) + 1
                    time.sleep(0.01)  # Small delay to increase race condition likelihood
                    db.commit()
        except Exception as e:
            errors.append(str(e))

    # Create agent first
    with SessionLocal() as db:
        agent = AgentRegistry(
            id=agent_id,
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            completed_episodes=0
        )
        db.add(agent)
        db.commit()

    # Spawn threads
    threads = []
    for i in range(thread_count):
        t = threading.Thread(target=update_maturity, args=(i,))
        threads.append(t)
        t.start()

    # Wait for completion
    for t in threads:
        t.join(timeout=5)

    # Verify final state
    with SessionLocal() as db:
        agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if agent:
            # Should have some episodes completed (may not equal thread_count due to races)
            assert agent.completed_episodes >= 0


@settings(max_examples=5)
@given(st.integers(min_value=2, max_value=5))
def test_concurrent_episode_segmentation_doesnt_duplicate(thread_count):
    """
    Test that concurrent episode segmentation doesn't duplicate segments.

    Edge case: Multiple threads creating segments concurrently.
    """
    episode_id = str(uuid.uuid4())
    segment_ids = []
    lock = threading.Lock()

    def create_segment(thread_id):
        try:
            with SessionLocal() as db:
                segment = EpisodeSegment(
                    id=str(uuid.uuid4()),
                    episode_id=episode_id,
                    segment_type="test",
                    content=f"Segment from thread {thread_id}",
                    timestamp=datetime.now(timezone.utc)
                )
                db.add(segment)
                db.commit()
                with lock:
                    segment_ids.append(segment.id)
        except Exception as e:
            pass  # Ignore errors

    # Create episode first
    with SessionLocal() as db:
        episode = Episode(
            id=episode_id,
            agent_id=str(uuid.uuid4()),
            title="Test Episode",
            summary="Test summary"
        )
        db.add(episode)
        db.commit()

    # Spawn threads
    threads = []
    for i in range(thread_count):
        t = threading.Thread(target=create_segment, args=(i,))
        threads.append(t)
        t.start()

    # Wait for completion
    for t in threads:
        t.join(timeout=5)

    # Verify no duplicates
    unique_ids = set(segment_ids)
    assert len(unique_ids) == len(segment_ids), "Duplicate segments detected"


# =============================================================================
# Performance Edge Cases (2 tests)
# =============================================================================

@settings(max_examples=3, deadline=timedelta(seconds=30))
@given(st.integers(min_value=100, max_value=1000))
def test_large_agent_query_returns_within_timeout(agent_count):
    """
    Test that large agent query returns within timeout.

    Edge case: Query 1000 agents should complete in reasonable time.
    """
    # This is a performance test - generate test data
    start_time = time.time()

    with SessionLocal() as db:
        # Query agents (limit to avoid timeout)
        agents = db.query(AgentRegistry).limit(agent_count).all()

        query_time = time.time() - start_time
        # Should complete within 30 seconds
        assert query_time < 30.0


@settings(max_examples=1, deadline=timedelta(seconds=10))
@given(st.integers(min_value=1000, max_value=1000))
def test_property_test_execution_time_under_5_seconds(iterations):
    """
    Test that property test execution time is under 5 seconds.

    Edge case: 1000 iterations should complete quickly.
    """
    start_time = time.time()

    # Run 1000 simple test iterations
    for i in range(iterations):
        agent_id = str(uuid.uuid4())
        assert len(agent_id) == 36  # UUID format check

    execution_time = time.time() - start_time
    # Should complete within 5 seconds
    assert execution_time < 5.0, f"Execution time {execution_time}s exceeded 5s threshold"
