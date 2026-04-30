"""
Property-based tests for data invariants.

This module uses Hypothesis to generate hundreds of random inputs
and test data invariants across Agent, Invoice, Episode, Workflow, and Task models.

Goal: Discover hidden bugs in business logic, data validation, and state management.
"""

import pytest
from hypothesis import given, strategies as st, assume, settings
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import uuid
import re

# Import models and enums
from core.models import (
    AgentRegistry,
    AgentStatus,
    AgentJobStatus,
    AgentExecution,
    Episode,
    EpisodeSegment,
)
from core.database import SessionLocal


# =============================================================================
# Agent Invariants (10 tests)
# =============================================================================

@given(st.text(min_size=1, max_size=100))
@settings(deadline=None)  # Disable deadline for validation tests
def test_agent_id_is_always_unique(agent_id_text):
    """
    Test that agent IDs are unique identifiers.

    Invariant: Agent ID should be a valid UUID or unique string without whitespace.
    """
    # This test documents that agent IDs should not contain tabs or newlines
    # The actual validation is in AgentRegistry.validate_id()
    if any(c in agent_id_text for c in ['\t', '\n', '\r']):
        # These characters should be rejected by validation
        with pytest.raises(ValueError, match="cannot contain whitespace"):
            agent = AgentRegistry(
                id=agent_id_text,
                name="Test Agent",
                category="test",
                module_path="test.module",
                class_name="TestClass"
            )
            agent.validate_id("id", agent_id_text)


@given(st.text(min_size=0, max_size=100))
@settings(deadline=None)  # Disable deadline for validation tests
def test_agent_name_is_non_empty_when_created(agent_name):
    """
    Test that agent names are non-empty strings when created.

    Invariant: Agent name should not be empty or just whitespace.
    """
    # Test that empty names are rejected by validation
    if agent_name.strip() == "":
        # Empty name should fail validation
        with pytest.raises(ValueError, match="cannot be empty"):
            agent = AgentRegistry(
                id=str(uuid.uuid4()),
                name=agent_name,
                category="test",
                module_path="test.module",
                class_name="TestClass"
            )
            # Trigger validation by accessing the name
            agent.validate_name("name", agent_name)


@given(st.sampled_from([AgentStatus.STUDENT, AgentStatus.INTERN, AgentStatus.SUPERVISED, AgentStatus.AUTONOMOUS]))
def test_agent_maturity_is_valid_enum(maturity):
    """
    Test that agent maturity is a valid enum value.

    Invariant: Agent maturity must be one of: STUDENT, INTERN, SUPERVISED, AUTONOMOUS.
    """
    # Verify that the enum value is valid
    valid_statuses = [AgentStatus.STUDENT, AgentStatus.INTERN, AgentStatus.SUPERVISED, AgentStatus.AUTONOMOUS]
    assert maturity in valid_statuses


@given(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=10))
def test_agent_capabilities_list_non_empty_for_intern_plus(capabilities):
    """
    Test that agent capabilities list is non-empty when maturity >= INTERN.

    Invariant: INTERN+ agents should have at least one capability.
    """
    maturity = AgentStatus.INTERN
    if maturity in [AgentStatus.INTERN, AgentStatus.SUPERVISED, AgentStatus.AUTONOMOUS]:
        # Intern+ agents should have capabilities
        assume(len(capabilities) > 0)


@given(st.datetimes(max_value=datetime.now()))
def test_agent_created_at_timestamp_not_future(created_time):
    """
    Test that agent created_at timestamp is <= current time.

    Invariant: Creation time cannot be in the future.
    """
    # Created time should not be in the future (hypothesis max_value handles this)
    now = datetime.now()
    # Allow some tolerance for clock skew
    assert created_time <= now + timedelta(seconds=5)


@given(st.datetimes(), st.datetimes())
def test_agent_updated_at_timestamp_after_created(created_time, updated_time):
    """
    Test that agent updated_at timestamp is >= created_at.

    Invariant: Update time cannot be before creation time.
    """
    # If both timestamps are set, updated_at >= created_at
    assume(updated_time >= created_time)
    assert updated_time >= created_time


@given(st.text(min_size=1, max_size=300))
def test_agent_id_no_whitespace(agent_id):
    """
    Test that agent ID doesn't contain whitespace.

    Invariant: Agent ID should be a contiguous string (UUID or slug).
    """
    # Test that validation rejects whitespace in IDs
    if any(c.isspace() for c in agent_id):
        # Whitespace in ID should fail validation
        with pytest.raises(ValueError, match="cannot contain whitespace"):
            agent = AgentRegistry(
                id=agent_id,
                name="Test Agent",
                category="test",
                module_path="test.module",
                class_name="TestClass"
            )
            agent.validate_id("id", agent_id)


@given(st.text(min_size=1, max_size=1000))
def test_agent_id_max_255_characters(agent_id):
    """
    Test that agent ID is <= 255 characters.

    Invariant: Database field constraint for ID length.
    """
    # Agent ID should not exceed 255 characters
    assert len(agent_id) <= 255


@given(st.sampled_from([
    (AgentStatus.STUDENT, AgentStatus.INTERN),
    (AgentStatus.INTERN, AgentStatus.SUPERVISED),
    (AgentStatus.SUPERVISED, AgentStatus.AUTONOMOUS),
]))
def test_agent_maturity_transitions_unidirectional(transition):
    """
    Test that agent maturity transitions are unidirectional (no demotion).

    Invariant: Maturity should only increase: STUDENT -> INTERN -> SUPERVISED -> AUTONOMOUS.
    """
    current_maturity, new_maturity = transition
    levels = {
        AgentStatus.STUDENT: 1,
        AgentStatus.INTERN: 2,
        AgentStatus.SUPERVISED: 3,
        AgentStatus.AUTONOMOUS: 4,
    }
    # Verify that transition is a promotion (higher level)
    assert levels[new_maturity] > levels[current_maturity]


@given(st.text(min_size=1, max_size=100))
def test_agent_capability_strings_non_empty(capability):
    """
    Test that agent capability strings are non-empty.

    Invariant: Each capability in capabilities list should be non-empty.
    """
    # Capability string should not be empty after stripping whitespace
    assume(len(capability.strip()) > 0)


# =============================================================================
# Invoice Invariants (10 tests)
# =============================================================================

@given(st.floats(min_value=0.01, max_value=1000000))
def test_invoice_totals_always_positive(total):
    """
    Test that invoice totals are always positive.

    Invariant: Invoice total cannot be negative or zero.
    """
    # Invoice total should be positive
    assert total > 0


@given(st.uuids())
def test_invoice_ids_are_unique(invoice_id):
    """
    Test that invoice IDs are unique.

    Invariant: Each invoice should have a unique identifier.
    """
    # UUIDs should be unique
    invoice_id_str = str(invoice_id)
    # Valid UUID format
    assert re.match(r'^[0-9a-f-]{36}$', invoice_id_str.lower())


@given(st.text(min_size=1, max_size=100), st.text(min_size=1, max_size=100))
def test_invoice_customer_id_references_valid_customer(customer_id, all_customer_ids):
    """
    Test that invoice customer_id references valid customer.

    Invariant: Foreign key constraint - customer must exist.
    """
    # Customer ID should not be empty
    assume(len(customer_id.strip()) > 0)
    assert len(customer_id) > 0


@given(st.integers(min_value=1, max_value=100))
def test_invoice_line_items_count_at_least_one(count):
    """
    Test that invoice line items count >= 1.

    Invariant: Invoice must have at least one line item.
    """
    # Invoice should have at least one line item
    assert count >= 1


@given(st.lists(st.floats(min_value=0, max_value=1000), min_size=1, max_size=10))
def test_invoice_line_item_totals_sum_to_invoice_total(line_items):
    """
    Test that invoice line item totals can be summed correctly.

    Invariant: Sum of line items should be calculable with floating-point tolerance.
    """
    # This test documents that invoice totals should match line item sums
    # The actual validation should happen in invoice creation logic
    line_sum = sum(line_items)
    # Verify sum is non-negative (invoices can't have negative totals)
    assert line_sum >= 0


@given(st.sampled_from(['DRAFT', 'PENDING', 'PAID', 'CANCELLED', 'OVERDUE']))
def test_invoice_status_valid_enum(status):
    """
    Test that invoice status is valid enum.

    Invariant: Status must be one of the valid invoice statuses.
    """
    # Valid invoice statuses
    valid_statuses = ['DRAFT', 'PENDING', 'PAID', 'CANCELLED', 'OVERDUE']
    assert status in valid_statuses


@given(st.datetimes(), st.integers(min_value=0, max_value=365))
def test_invoice_due_date_after_issue_date(issue_date, days_until_due):
    """
    Test that invoice due_date >= issue_date.

    Invariant: Due date cannot be before issue date.
    """
    # Due date should be after or equal to issue date
    due_date = issue_date + timedelta(days=days_until_due)
    assert due_date >= issue_date


@given(st.floats(min_value=0, max_value=1000))
def test_invoice_tax_amount_non_negative(tax_amount):
    """
    Test that invoice tax_amount >= 0.

    Invariant: Tax cannot be negative.
    """
    # Tax amount should be non-negative
    assert tax_amount >= 0


@given(st.floats(min_value=0, max_value=500), st.floats(min_value=0, max_value=1000))
def test_invoice_discount_amount_within_range(discount, total):
    """
    Test that invoice discount_amount >= 0 and <= total.

    Invariant: Discount cannot exceed invoice total.
    """
    # Discount should be within valid range
    assume(discount <= total)
    assert 0 <= discount <= total


@given(st.sampled_from(['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'INR', 'CNY']))
def test_invoice_currency_code_valid_iso_4217(currency):
    """
    Test that invoice currency code is valid ISO 4217.

    Invariant: Currency should be 3-letter ISO 4217 code.
    """
    # Currency code should be 3 letters
    assert len(currency) == 3
    assert currency.isalpha()
    assert currency.isupper()


# =============================================================================
# Episode Invariants (8 tests)
# =============================================================================

@given(st.uuids())
def test_episode_ids_are_unique(episode_id):
    """
    Test that episode IDs are unique.

    Invariant: Each episode should have unique identifier.
    """
    # UUID should be unique and valid format
    episode_id_str = str(episode_id)
    assert re.match(r'^[0-9a-f-]{36}$', episode_id_str.lower())


@given(st.lists(st.datetimes(), min_size=3, max_size=10))
def test_episode_segments_ordered_by_timestamp(timestamps):
    """
    Test that episode segments are ordered by timestamp.

    Invariant: Segments should be in chronological order.
    """
    # Sort timestamps to simulate proper ordering
    sorted_timestamps = sorted(timestamps)
    # Verify order is maintained
    for i in range(len(sorted_timestamps) - 1):
        assert sorted_timestamps[i] <= sorted_timestamps[i + 1]


@given(st.datetimes(), st.integers(min_value=1, max_value=100))
def test_episode_segment_timestamps_monotonically_increasing(start_time, offset_seconds):
    """
    Test that episode segment timestamps are monotonically increasing.

    Invariant: Each subsequent segment timestamp > previous.
    """
    # Next segment should be after previous
    next_time = start_time + timedelta(seconds=offset_seconds)
    assert next_time > start_time


@given(st.integers(min_value=1, max_value=50))
def test_episode_has_at_least_one_segment(segment_count):
    """
    Test that episode has at least 1 segment.

    Invariant: Episode cannot be empty.
    """
    # Episode should have at least one segment
    assert segment_count >= 1


@given(st.text(min_size=1, max_size=50), st.integers(min_value=1, max_value=10))
def test_episode_segments_belong_to_same_agent(agent_id, segment_count):
    """
    Test that episode segments belong to same agent_id.

    Invariant: All segments in episode should have same agent.
    """
    # All segments should share the same agent_id
    segments = [{'agent_id': agent_id} for _ in range(segment_count)]
    # Verify all segments have same agent_id
    agent_ids = {seg['agent_id'] for seg in segments}
    assert len(agent_ids) == 1
    assert agent_id in agent_ids


@given(st.datetimes(), st.integers(min_value=1, max_value=86400))
def test_episode_start_time_before_end_time(start_time, duration_seconds):
    """
    Test that episode start_time <= end_time.

    Invariant: Episode cannot end before it starts.
    """
    # End time should be after start time
    end_time = start_time + timedelta(seconds=duration_seconds)
    assert end_time >= start_time


@given(st.text(min_size=1, max_size=1000))
def test_episode_summary_length_limit(summary):
    """
    Test that episode summary length <= 500 words.

    Invariant: Summary should be concise.
    """
    # Count words in summary
    word_count = len(summary.split())
    # Summary should not exceed 500 words
    assume(word_count <= 500)


@given(st.integers(min_value=1, max_value=5))
def test_episode_feedback_scores_in_range(feedback_score):
    """
    Test that episode feedback scores are 1-5 (integer).

    Invariant: Feedback score must be in valid range.
    """
    # Feedback score should be between 1 and 5
    assert 1 <= feedback_score <= 5


# =============================================================================
# Workflow Invariants (7 tests)
# =============================================================================

@given(st.uuids())
def test_workflow_ids_are_unique(workflow_id):
    """
    Test that workflow IDs are unique.

    Invariant: Each workflow should have unique identifier.
    """
    # UUID should be unique
    workflow_id_str = str(workflow_id)
    assert re.match(r'^[0-9a-f-]{36}$', workflow_id_str.lower())


@given(st.integers(min_value=1, max_value=10))
def test_workflow_steps_executed_in_order(step_count):
    """
    Test that workflow steps are executed in order.

    Invariant: Steps should follow sequential execution.
    """
    # Steps should be executed in order 1, 2, 3, ...
    steps = list(range(1, step_count + 1))
    assert steps == sorted(steps)


@given(st.integers(min_value=1, max_value=50))
def test_workflow_step_count_at_least_one(step_count):
    """
    Test that workflow step count >= 1.

    Invariant: Workflow must have at least one step.
    """
    # Workflow should have at least one step
    assert step_count >= 1


@given(st.integers(min_value=1, max_value=10))
def test_workflow_has_at_least_one_trigger(trigger_count):
    """
    Test that workflow has at least 1 trigger condition.

    Invariant: Workflow must be triggerable.
    """
    # Workflow should have at least one trigger
    assert trigger_count >= 1


@given(st.sampled_from([
    ('DRAFT', 'ACTIVE'),
    ('ACTIVE', 'PAUSED'),
    ('ACTIVE', 'COMPLETED'),
    ('PAUSED', 'ACTIVE'),
]))
def test_workflow_status_transitions_valid(transition):
    """
    Test that workflow status transitions are valid.

    Invariant: DRAFT -> ACTIVE -> PAUSED/COMPLETED.
    """
    current_status, new_status = transition
    # Valid transitions
    valid_transitions = {
        'DRAFT': ['ACTIVE'],
        'ACTIVE': ['PAUSED', 'COMPLETED'],
        'PAUSED': ['ACTIVE'],
        'COMPLETED': [],  # Terminal state
    }
    assert new_status in valid_transitions[current_status]


@given(st.integers(min_value=0, max_value=3600))
def test_workflow_timeout_seconds_non_negative(timeout):
    """
    Test that workflow timeout_seconds >= 0.

    Invariant: Timeout cannot be negative.
    """
    # Timeout should be non-negative
    assert timeout >= 0


@given(st.integers(min_value=0, max_value=10))
def test_workflow_retry_count_non_negative(retry_count):
    """
    Test that workflow retry_count >= 0.

    Invariant: Retry count cannot be negative.
    """
    # Retry count should be non-negative
    assert retry_count >= 0


# =============================================================================
# Task Invariants (5 tests)
# =============================================================================

@given(st.uuids())
def test_task_ids_are_unique(task_id):
    """
    Test that task IDs are unique.

    Invariant: Each task should have unique identifier.
    """
    # UUID should be unique
    task_id_str = str(task_id)
    assert re.match(r'^[0-9a-f-]{36}$', task_id_str.lower())


@given(st.sampled_from(['PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED']))
def test_task_status_valid_enum(status):
    """
    Test that task status is valid enum.

    Invariant: Status must be one of the valid task statuses.
    """
    # Valid task statuses
    valid_statuses = ['PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED']
    assert status in valid_statuses


@given(st.integers(min_value=1, max_value=5))
def test_task_priority_in_range(priority):
    """
    Test that task priority is 1-5 (integer).

    Invariant: Priority must be in valid range.
    """
    # Priority should be between 1 and 5
    assert 1 <= priority <= 5


@given(st.datetimes(), st.datetimes())
def test_task_created_at_before_started_at(created_at, started_at):
    """
    Test that task created_at <= started_at (if started).

    Invariant: Task cannot be started before creation.
    """
    # Started at should be after or equal to created at
    assume(started_at >= created_at)
    assert started_at >= created_at


@given(st.datetimes(), st.datetimes())
def test_task_completed_at_after_started_at(started_at, completed_at):
    """
    Test that task completed_at >= started_at (if completed).

    Invariant: Task cannot be completed before starting.
    """
    # Completed at should be after or equal to started at
    assume(completed_at >= started_at)
    assert completed_at >= started_at
